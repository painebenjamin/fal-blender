# SPDX-License-Identifier: Apache-2.0
"""Realtime viewport refinement via Klein WebSocket streaming.

Captures the 3D viewport at regular intervals, sends frames through
Klein's realtime img2img endpoint, and displays refined results in
the Image Editor.
"""

from __future__ import annotations

import base64
import io
import queue
import threading
import time
from typing import Any

import bpy
import gpu
from gpu_extras.presets import draw_texture_2d

from ..preferences import ensure_api_key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Application ID without /realtime — the client.realtime() method
# appends path="/realtime" by default
KLEIN_REALTIME_APP = "fal-ai/flux-2/klein"
DEFAULT_SYSTEM_PROMPT = (
    "You are presented with a 3D-rendered image. Recreate this image in a "
    "photorealistic manner, being sure to represent the original artistic "
    "intent, only using a photorealistic style. Adjust lighting to be more "
    "realistic while adding details and texture where appropriate."
)

# Klein realtime optimal: 704x704 JPEG at 50% quality
CAPTURE_SIZE = 704
JPEG_QUALITY = 50


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class FalRealtimeRefineProperties(bpy.types.PropertyGroup):
    is_active: bpy.props.BoolProperty(
        name="Active",
        description="Whether realtime refinement is currently streaming",
        default=False,
    )

    system_prompt: bpy.props.StringProperty(
        name="System Prompt",
        description="Instructions for how the AI should refine the viewport",
        default=DEFAULT_SYSTEM_PROMPT,
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Additional guidance for the refinement",
        default="",
    )

    target_fps: bpy.props.IntProperty(
        name="Target FPS",
        description="Target frames per second for capture (actual rate depends on inference speed)",
        default=4,
        min=1,
        max=15,
    )

    image_size: bpy.props.EnumProperty(
        name="Size",
        items=[
            ("square", "704×704", "Square output (faster)"),
            ("square_hd", "1024×1024", "HD square output"),
        ],
        default="square",
        description="Output resolution for realtime refinement",
    )

    num_inference_steps: bpy.props.IntProperty(
        name="Steps",
        description="Inference steps (fewer = faster, more = higher quality)",
        default=3,
        min=1,
        max=8,
    )

    feedback_strength: bpy.props.FloatProperty(
        name="Temporal Stability",
        description="Temporal coherence between frames. Lower = smoother/stable, Higher = more responsive",
        default=0.85,
        min=0.0,
        max=1.0,
        step=5,
        precision=2,
    )


# ---------------------------------------------------------------------------
# Realtime session manager (runs in background thread)
# ---------------------------------------------------------------------------

class _RealtimeSession:
    """Manages the WebSocket connection to Klein realtime in a background thread."""

    def __init__(self) -> None:
        self._send_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=2)
        self._result_queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: str | None = None
        self._frames_sent = 0
        self._frames_received = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def stats(self) -> tuple[int, int]:
        return self._frames_sent, self._frames_received

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._error = None
        self._frames_sent = 0
        self._frames_received = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def send_frame(self, payload: dict[str, Any]) -> bool:
        """Submit a frame for processing. Returns False if queue is full (drop frame)."""
        try:
            # Drop oldest if queue is full (we always want the latest frame)
            if self._send_queue.full():
                try:
                    self._send_queue.get_nowait()
                except queue.Empty:
                    pass
            self._send_queue.put_nowait(payload)
            return True
        except queue.Full:
            return False

    def get_result(self) -> bytes | None:
        """Get the latest result image bytes, or None if no result ready."""
        result = None
        # Drain to get latest result only
        while True:
            try:
                result = self._result_queue.get_nowait()
            except queue.Empty:
                break
        return result

    def _run(self) -> None:
        """Background thread: manage WebSocket connection and send/receive frames."""
        try:
            import fal_client

            ensure_api_key()
            client = fal_client.SyncClient()
            print(f"fal.ai realtime: connecting to {KLEIN_REALTIME_APP}...")

            with client.realtime(KLEIN_REALTIME_APP, max_buffering=1) as connection:
                print("fal.ai realtime: connected!")
                while not self._stop_event.is_set():
                    # Check for frame to send
                    try:
                        payload = self._send_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    # Send frame
                    try:
                        connection.send(payload)
                        self._frames_sent += 1
                        if self._frames_sent <= 3:
                            print(f"fal.ai realtime: sent frame {self._frames_sent} "
                                  f"(image_url len={len(payload.get('image_url', ''))})")
                    except Exception as e:
                        print(f"fal.ai realtime: send error: {e}")
                        self._error = f"Send failed: {e}"
                        break

                    # Wait for result
                    try:
                        result = connection.recv()
                        if result is None:
                            continue
                        if "error" in result:
                            print(f"fal.ai realtime: server error: {result['error']}")
                            continue
                        if "images" in result:
                            images = result["images"]
                            if images:
                                content = images[0].get("content", "")
                                if content:
                                    image_bytes = base64.b64decode(content)
                                    # Drop oldest result if full
                                    if self._result_queue.full():
                                        try:
                                            self._result_queue.get_nowait()
                                        except queue.Empty:
                                            pass
                                    self._result_queue.put_nowait(image_bytes)
                                    self._frames_received += 1
                                    if self._frames_received <= 3:
                                        print(f"fal.ai realtime: received frame {self._frames_received} "
                                              f"({len(image_bytes)} bytes)")
                                else:
                                    print(f"fal.ai realtime: empty content in result")
                        elif self._frames_received == 0:
                            print(f"fal.ai realtime: unexpected result format: {list(result.keys())}")
                    except Exception as e:
                        print(f"fal.ai realtime: receive error: {e}")

        except Exception as e:
            self._error = str(e)
            import traceback
            print(f"fal.ai realtime: connection error: {e}")
            traceback.print_exc()


# Module-level session instance
_session = _RealtimeSession()


# ---------------------------------------------------------------------------
# Viewport capture utilities
# ---------------------------------------------------------------------------

def _capture_viewport_as_data_uri(context: bpy.types.Context, size: int) -> str | None:
    """Capture the 3D viewport as a JPEG base64 data URI.

    Uses gpu.offscreen to render the viewport at the specified size.
    Returns data:image/jpeg;base64,... or None on failure.
    """
    # Find the 3D viewport
    area = None
    for a in context.screen.areas:
        if a.type == "VIEW_3D":
            area = a
            break
    if area is None:
        return None

    space = area.spaces.active
    region = None
    for r in area.regions:
        if r.type == "WINDOW":
            region = r
            break
    if region is None:
        return None

    # Create offscreen buffer
    offscreen = gpu.types.GPUOffScreen(size, size)

    try:
        offscreen.draw_view3d(
            context.scene,
            context.view_layer,
            space,
            region,
            context.scene.camera.matrix_world if context.scene.camera else
            space.region_3d.view_matrix.inverted(),
            space.region_3d.window_matrix,
            do_color_management=True,
            draw_background=True,
        )

        # Read pixels
        buffer = offscreen.texture_color.read()
        # buffer is a Buffer object with RGBA float data
        # Convert to bytes
        import numpy as np
        from PIL import Image

        pixels = np.array(buffer.to_list(), dtype=np.float32)
        pixels = pixels.reshape(size, size, 4)
        # Flip Y (OpenGL convention)
        pixels = np.flip(pixels, axis=0)
        # Convert to uint8 RGB
        rgb = (pixels[:, :, :3] * 255).clip(0, 255).astype(np.uint8)

        img = Image.fromarray(rgb)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    finally:
        offscreen.free()


def _load_result_image(image_bytes: bytes, image_name: str = "fal Realtime") -> None:
    """Load JPEG bytes into a Blender image for display."""
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    # Get or create the Blender image
    bl_img = bpy.data.images.get(image_name)
    if bl_img is None or bl_img.size[0] != w or bl_img.size[1] != h:
        if bl_img is not None:
            bpy.data.images.remove(bl_img)
        bl_img = bpy.data.images.new(image_name, w, h)

    # Convert PIL to flat RGBA float array
    rgba = np.array(img.convert("RGBA"), dtype=np.float32) / 255.0
    # Flip Y for Blender convention
    rgba = np.flip(rgba, axis=0)
    bl_img.pixels.foreach_set(rgba.ravel())
    bl_img.update()


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class FAL_OT_realtime_refine_start(bpy.types.Operator):
    bl_idname = "fal.realtime_refine_start"
    bl_label = "Start Realtime Refine"
    bl_description = "Start streaming viewport through Klein realtime for AI refinement"

    _timer = None

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_realtime_refine
        return not props.is_active

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_realtime_refine

        # Cache properties for the timer (avoid accessing RNA from wrong context)
        system = props.system_prompt.strip()
        user = props.prompt.strip()
        if system and user:
            self._full_prompt = f'{system}\n\nFollow the user\'s prompt: "{user}"'
        elif system:
            self._full_prompt = system
        else:
            self._full_prompt = user or "photorealistic rendering"

        self._image_size = props.image_size
        self._num_steps = props.num_inference_steps
        self._feedback = props.feedback_strength
        self._capture_size = CAPTURE_SIZE if props.image_size == "square" else 1024
        self._interval = 1.0 / max(1, props.target_fps)
        self._last_send_time = 0.0

        # Start the WebSocket session
        _session.start()
        props.is_active = True

        # Register modal timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(self._interval, window=context.window)
        wm.modal_handler_add(self)

        self.report({"INFO"}, "Realtime refine started")
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        props = context.scene.fal_realtime_refine

        # Check if we should stop
        if not props.is_active or not _session.is_running:
            self._cleanup(context)
            if _session.error:
                self.report({"ERROR"}, f"Realtime error: {_session.error}")
            return {"CANCELLED"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        now = time.monotonic()

        # Capture and send viewport frame
        if now - self._last_send_time >= self._interval:
            data_uri = _capture_viewport_as_data_uri(context, self._capture_size)
            if data_uri:
                payload = {
                    "prompt": self._full_prompt,
                    "image_url": data_uri,
                    "image_size": self._image_size,
                    "num_inference_steps": self._num_steps,
                    "output_feedback_strength": self._feedback,
                }
                _session.send_frame(payload)
                self._last_send_time = now

        # Check for results
        result_bytes = _session.get_result()
        if result_bytes is not None:
            _load_result_image(result_bytes)
            # Force redraw of image editors
            for area in context.screen.areas:
                if area.type == "IMAGE_EDITOR":
                    area.tag_redraw()

        return {"PASS_THROUGH"}

    def _cleanup(self, context: bpy.types.Context) -> None:
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.scene.fal_realtime_refine.is_active = False


class FAL_OT_realtime_refine_stop(bpy.types.Operator):
    bl_idname = "fal.realtime_refine_stop"
    bl_label = "Stop Realtime Refine"
    bl_description = "Stop the realtime refinement stream"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_realtime_refine
        return props.is_active

    def execute(self, context: bpy.types.Context) -> set[str]:
        _session.stop()
        context.scene.fal_realtime_refine.is_active = False
        sent, received = _session.stats
        self.report({"INFO"}, f"Realtime refine stopped ({sent} sent, {received} received)")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

CLASSES = [
    FalRealtimeRefineProperties,
    FAL_OT_realtime_refine_start,
    FAL_OT_realtime_refine_stop,
]


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_realtime_refine = bpy.props.PointerProperty(
        type=FalRealtimeRefineProperties,
    )


def unregister() -> None:
    if hasattr(bpy.types.Scene, "fal_realtime_refine"):
        del bpy.types.Scene.fal_realtime_refine
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
