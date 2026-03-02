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
        self._future = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def submit(self):
        """Submit the job to the thread pool."""
        self.status = "running"
        self._future = _executor.submit(self._run)

    def _run(self):
        """Execute in background thread — no bpy calls allowed here!"""
        import fal_client

        # Ensure API key is set
        from ..preferences import ensure_api_key

        ensure_api_key()

        try:

            def _on_queue_update(update):
                if isinstance(update, fal_client.InProgress):
                    if update.logs:
                        last = update.logs[-1]
                        msg = last.get("message", "") if isinstance(last, dict) else str(last)
                        self.progress_message = msg[:80]

            result = fal_client.subscribe(
                self.endpoint,
                arguments=self.arguments,
                with_logs=True,
                on_queue_update=_on_queue_update,
            )
            self.result = result

            # Download any URL fields to local temp files
            self._download_results(result)

            self.status = "complete"

        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.status = "error"
            traceback.print_exc()

    def _download_results(self, result: dict[str, Any]):
        """Download URLs from result dict to local temp files."""
        import urllib.request

        for key in self.download_keys:
            url = self._extract_url(result, key)
            if not url:
                continue

            # Determine extension from URL
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
        self.history: list[FalJob] = []  # completed jobs (last N)
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
        """Submit a job for execution."""
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

        for job_id, job in self.jobs.items():
            if job.is_done:
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
            del self.jobs[jid]

        if self.jobs:
            # Redraw 3D viewports to update progress
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
            return 0.5
        else:
            self._timer_running = False
            return None  # stop timer

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
