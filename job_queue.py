# SPDX-License-Identifier: Apache-2.0
"""Async job queue — runs fal API calls in background threads,
polls via bpy.app.timers, processes results on the main thread."""

from __future__ import annotations

import os
import uuid
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    pass

import bpy  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Thread pool — shared across all jobs
# ---------------------------------------------------------------------------
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="fal")


# ---------------------------------------------------------------------------
# Error formatting (module-level helper)
# ---------------------------------------------------------------------------
def _format_error(e: Exception) -> str:
    """Extract useful error details from fal_client exceptions."""
    error_type = type(e).__name__
    msg = str(e)

    status_code = getattr(e, "status_code", None) or getattr(e, "status", None)
    body = getattr(e, "body", None) or getattr(e, "detail", None)

    response = getattr(e, "response", None)
    if response is not None:
        if status_code is None:
            status_code = getattr(response, "status_code", None)
        if body is None:
            try:
                body = response.json()
            except Exception:
                try:
                    body = response.text[:500]
                except Exception:
                    pass

    parts = []
    if status_code:
        parts.append(f"HTTP {status_code}")
    if body:
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or body.get("error")
            if isinstance(detail, str):
                parts.append(detail)
            elif isinstance(detail, list) and detail:
                parts.append("; ".join(
                    d.get("msg", str(d)) for d in detail[:3]
                ))
            else:
                parts.append(str(body)[:300])
        else:
            parts.append(str(body)[:300])
    elif msg and msg != str(status_code):
        parts.append(msg[:300])

    if parts:
        return f"{error_type}: {' — '.join(parts)}"
    return f"{error_type}: {msg[:300]}"


# ---------------------------------------------------------------------------
# FalJob
# ---------------------------------------------------------------------------
class FalJob:
    """Tracks a single fal API request running in a background thread."""

    def __init__(
        self,
        endpoint: str,
        arguments: dict[str, Any],
        on_complete: Callable[["FalJob"], None],
        *,
        job_id: str | None = None,
        label: str = "",
        download_keys: list[str] | None = None,
    ):
        self.job_id = job_id or uuid.uuid4().hex[:12]
        self.endpoint = endpoint
        self.arguments = arguments
        self.on_complete = on_complete
        self.label = label or endpoint
        self.download_keys = download_keys or []

        self.status: str = "pending"  # pending | running | complete | error
        self.progress: float = 0.0
        self.progress_message: str = ""
        self.result: dict[str, Any] | None = None
        self.downloaded_files: dict[str, str] = {}  # key → local path
        self.error: str | None = None
        self.request_id: str | None = None  # fal request ID for server-side debugging
        self._future = None
        self._api_key: str | None = None  # cached on main thread before submit

    # ── Lifecycle ──────────────────────────────────────────────────────

    def submit(self):
        """Submit the job to the thread pool.

        MUST be called from the main thread — caches the API key
        before spawning the background thread.
        """
        from .preferences import ensure_api_key

        self._api_key = ensure_api_key()
        self.status = "running"
        self._future = _executor.submit(self._run)

    def _run(self):
        """Execute in background thread — no bpy calls allowed here!"""
        try:
            import fal_client
        except ImportError as e:
            self.error = f"fal_client not installed: {e}"
            self.status = "error"
            print(f"fal.ai: {self.error}")
            return

        if self._api_key:
            os.environ["FAL_KEY"] = self._api_key

        try:

            def _on_queue_update(update):
                if isinstance(update, fal_client.InProgress):
                    if update.logs:
                        last = update.logs[-1]
                        msg = (
                            last.get("message", "")
                            if isinstance(last, dict)
                            else str(last)
                        )
                        self.progress_message = msg[:80]

            def _on_enqueue(request_id: str):
                self.request_id = request_id
                print(f"fal.ai: {self.endpoint} enqueued as {request_id}")

            print(
                f"fal.ai: Calling {self.endpoint} "
                f"with {list(self.arguments.keys())}"
            )
            result = fal_client.subscribe(
                self.endpoint,
                arguments=self.arguments,
                with_logs=True,
                on_enqueue=_on_enqueue,
                on_queue_update=_on_queue_update,
            )
            self.result = result
            print(
                f"fal.ai: {self.endpoint} [{self.request_id or '?'}] returned: "
                f"{list(result.keys()) if isinstance(result, dict) else type(result)}"
            )

            self._download_results(result)
            self.status = "complete"

        except Exception as e:
            self.error = _format_error(e)
            self.status = "error"
            if self.request_id:
                self.error = f"[{self.request_id}] {self.error}"
            print(f"fal.ai: Job {self.job_id} [{self.request_id or '?'}] failed: {self.error}")
            traceback.print_exc()

    def _download_results(self, result: dict[str, Any]):
        """Download URLs from result dict to local temp files."""
        import urllib.request

        for key in self.download_keys:
            url = self._extract_url(result, key)
            if not url:
                continue

            ext = Path(url.split("?")[0]).suffix or ".bin"
            tmp = tempfile.NamedTemporaryFile(
                prefix=f"fal_{self.job_id}_",
                suffix=ext,
                delete=False,
            )
            tmp.close()

            try:
                urllib.request.urlretrieve(url, tmp.name)
                self.downloaded_files[key] = tmp.name
            except Exception as e:
                print(f"fal.ai: Failed to download {key}: {e}")

    @staticmethod
    def _extract_url(data: Any, key: str) -> str | None:
        """Extract a URL from nested result data.

        Supports dotted paths like 'model_mesh.url' and
        array access like 'images.0.url'.
        """
        parts = key.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return None
            else:
                return None
        return current if isinstance(current, str) else None

    @property
    def is_done(self) -> bool:
        return self.status in ("complete", "error")


# ---------------------------------------------------------------------------
# JobManager singleton
# ---------------------------------------------------------------------------
class JobManager:
    """Manages active fal jobs, polls completion via bpy.app.timers."""

    _instance: JobManager | None = None

    def __init__(self):
        self.jobs: dict[str, FalJob] = {}
        self.history: list[FalJob] = []
        self._timer_running = False
        self._max_history = 20

    @classmethod
    def get(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing / unregister)."""
        cls._instance = None

    def submit(self, job: FalJob) -> FalJob:
        """Submit a job for execution. Must be called from main thread."""
        self.jobs[job.job_id] = job
        job.submit()
        if not self._timer_running:
            bpy.app.timers.register(self._poll, first_interval=0.5)
            self._timer_running = True
        return job

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/running job (best-effort)."""
        job = self.jobs.get(job_id)
        if job and job._future:
            job._future.cancel()
            job.status = "error"
            job.error = "Cancelled"
            return True
        return False

    def _poll(self) -> float | None:
        """Timer callback — runs on the main thread."""
        done_ids = []

        # Snapshot keys — on_complete handlers may submit new jobs
        for job_id in list(self.jobs):
            job = self.jobs.get(job_id)
            if job is None or not job.is_done:
                continue
            done_ids.append(job_id)
            self.history.append(job)
            if len(self.history) > self._max_history:
                self.history.pop(0)
            try:
                job.on_complete(job)
            except Exception as e:
                print(f"fal.ai: Error in completion handler: {e}")
                traceback.print_exc()

        for jid in done_ids:
            self.jobs.pop(jid, None)

        if self.jobs:
            try:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()
            except Exception:
                pass
            return 0.5
        else:
            self._timer_running = False
            return None

    @property
    def active_count(self) -> int:
        return len(self.jobs)

    @property
    def active_jobs(self) -> list[FalJob]:
        return list(self.jobs.values())


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register():
    pass


def unregister():
    JobManager.reset()
