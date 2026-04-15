from __future__ import annotations

import os
import tempfile
from typing import Any, ClassVar

import bpy

from ...importers import add_video_to_vse
from ...job_queue import FalJob, JobManager
from ...models import DepthVideoModel, ImageToVideoModel, TextToVideoModel
from ...utils import (download_file, ensure_compositor_enabled,
                      get_compositor_node_tree, get_eevee_engine,
                      restore_compositor, snapshot_compositor,
                      upload_blender_image, upload_file)
from ..neural_render.utils import calc_scene_depth_bounds
from ..operators import FalOperator

TEXT_TO_VIDEO_MODELS = TextToVideoModel.catalog()
IMAGE_TO_VIDEO_MODELS = ImageToVideoModel.catalog()
DEPTH_VIDEO_MODELS = DepthVideoModel.catalog()


def _get_scene_duration(scene: bpy.types.Scene) -> float:
    """Calculate the scene duration in seconds from frame range and FPS."""
    fps = scene.render.fps / scene.render.fps_base
    frames = scene.frame_end - scene.frame_start + 1
    return frames / fps


def _get_scene_dimensions(scene: bpy.types.Scene) -> tuple[int, int]:
    """Return the effective render resolution as (width, height)."""
    scale = scene.render.resolution_percentage / 100.0
    return (
        int(scene.render.resolution_x * scale),
        int(scene.render.resolution_y * scale),
    )


# ---------------------------------------------------------------------------
# VSE operator: text-to-video and image-to-video (fire-and-forget)
# ---------------------------------------------------------------------------
class FalVideoOperator(FalOperator):
    """Operator for text-to-video and image-to-video generation via fal.ai."""

    label = "Generate Video"
    description = "Generate a video using fal.ai"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Return whether a valid prompt or image source is configured."""
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        else:  # IMAGE
            return bool(props.image_path.strip() or props.image_source == "RENDER")

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Dispatch to text-to-video or image-to-video based on the current mode."""
        if props.mode == "TEXT":
            return self._text_to_video(context, props)
        else:
            return self._image_to_video(context, props)

    def _get_duration(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> int:
        """Return the target video duration in seconds."""
        if props.use_scene_duration:
            return max(1, int(round(_get_scene_duration(context.scene))))
        return int(props.duration)

    def _text_to_video(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Submit a text-to-video generation job."""
        model = TEXT_TO_VIDEO_MODELS[props.text_endpoint]
        duration = self._get_duration(context, props)
        params = model.parameters(
            prompt=props.prompt,
            enable_prompt_expansion=props.enable_prompt_expansion,
            duration=duration,
        )

        def on_complete(job: FalJob) -> None:
            _handle_video_result(job)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Video: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Generating {duration}s video...")
        return {"FINISHED"}

    def _image_to_video(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Submit an image-to-video generation job."""
        if props.image_source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            image_url = upload_file(tmp.name)
        elif props.image_path:
            image_url = upload_file(bpy.path.abspath(props.image_path))
        else:
            self.report({"ERROR"}, "No image specified")
            return {"CANCELLED"}

        model = IMAGE_TO_VIDEO_MODELS[props.image_endpoint]
        duration = self._get_duration(context, props)
        params = model.parameters(
            prompt=props.prompt,
            enable_prompt_expansion=props.enable_prompt_expansion,
            image_url=image_url,
            duration=duration,
        )

        def on_complete(job: FalJob) -> None:
            _handle_video_result(job)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label="Video from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Generating {duration}s video from image...")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 3D panel operator: depth-conditioned video (modal render + API call)
# ---------------------------------------------------------------------------
class FalDepthVideoOperator(FalOperator):
    """Modal operator that renders a depth animation then submits it to fal.ai for video generation."""

    label = "Generate Depth Video"
    description = "Render depth animation and generate video via fal.ai"

    _rendering: ClassVar[bool] = False

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Return whether depth video generation can start (requires prompt and camera)."""
        if cls._rendering:
            return False
        return bool(props.prompt.strip()) and context.scene.camera is not None

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Set up and start a modal depth-render followed by fal.ai video generation."""
        if not invoke:
            self.report({"ERROR"}, "Depth video must be invoked from UI")
            return {"CANCELLED"}

        scene = context.scene
        if not scene.camera:
            self.report({"ERROR"}, "No camera in scene")
            return {"CANCELLED"}

        # Cache props — context/props may be stale inside render handlers
        self._prompt = props.prompt
        self._expand_prompt = props.enable_prompt_expansion
        self._endpoint = props.depth_endpoint
        self._model = DEPTH_VIDEO_MODELS[props.depth_endpoint]
        self._use_first_frame = props.depth_use_first_frame
        self._first_frame_source = props.depth_image_source
        self._first_frame_path = props.depth_image_path
        self._first_frame_texture = props.depth_texture_name

        if props.use_scene_duration:
            self._duration = max(1, int(round(_get_scene_duration(scene))))
        else:
            self._duration = int(props.duration)

        fps = scene.render.fps / scene.render.fps_base
        self._num_frames = max(17, int(self._duration * min(fps, 16)))

        if props.use_scene_resolution:
            w, h = _get_scene_dimensions(scene)
            if max(w, h) >= 1280:
                self._resolution = "720p"
            elif max(w, h) >= 580:
                self._resolution = "580p"
            else:
                self._resolution = "480p"
        else:
            self._resolution = None

        # Modal state
        self._render_done = False
        self._render_cancelled = False
        self._timer = None
        self._saved: dict[str, Any] = {}
        self._saved_compositor: list[dict] = []
        self._tmp_dir: str | None = None
        self._output_path: str | None = None

        # Pre-capture first-frame image BEFORE depth render overwrites
        # the Render Result with BW depth data
        self._first_frame_url: str | None = None
        if self._use_first_frame:
            self._first_frame_url = self._capture_first_frame()

        try:
            self._setup_depth_animation(context)
        except Exception as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Depth render setup failed: {e}")
            return {"CANCELLED"}

        type(self)._rendering = True

        self._handler_complete = self._on_complete
        self._handler_cancel = self._on_cancel
        bpy.app.handlers.render_complete.append(self._handler_complete)
        bpy.app.handlers.render_cancel.append(self._handler_cancel)

        bpy.ops.render.render("INVOKE_DEFAULT", animation=True)

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self._operator_instance)

        scene_dur = _get_scene_duration(scene)
        self.report(
            {"INFO"},
            f"Rendering depth animation ({scene_dur:.1f}s, {self._num_frames} frames)...",
        )
        return {"RUNNING_MODAL"}

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """Poll for render completion and finalize the depth video pipeline."""
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if not (self._render_done or self._render_cancelled):
            return {"PASS_THROUGH"}

        self._cleanup_modal(context)

        if self._render_cancelled:
            self._restore_state(context)
            self.report({"WARNING"}, "Depth render cancelled")
            return {"CANCELLED"}

        self._finish_depth_animation(context)
        return {"FINISHED"}

    # ── Render handlers ────────────────────────────────────────────────

    def _on_complete(self, *_args: Any) -> None:
        """Blender render-complete handler callback."""
        self._render_done = True

    def _on_cancel(self, *_args: Any) -> None:
        """Blender render-cancel handler callback."""
        self._render_cancelled = True

    def _cleanup_modal(self, context: bpy.types.Context) -> None:
        """Remove the modal timer and render handlers."""
        type(self)._rendering = False
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        for ref, handler_list in [
            (self._handler_complete, bpy.app.handlers.render_complete),
            (self._handler_cancel, bpy.app.handlers.render_cancel),
        ]:
            try:
                handler_list.remove(ref)
            except (ValueError, AttributeError):
                pass

    # ── Depth animation setup / finish ─────────────────────────────────

    def _setup_depth_animation(self, context: bpy.types.Context) -> None:
        """Configure Blender to render a mist/depth pass animation as video."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        camera = scene.camera

        self._saved.update(
            {
                "engine": scene.render.engine,
                "film_transparent": scene.render.film_transparent,
                "use_compositing": scene.render.use_compositing,
                "use_pass_mist": view_layer.use_pass_mist,
                "view_transform": scene.view_settings.view_transform,
                "look": scene.view_settings.look,
                "file_format": scene.render.image_settings.file_format,
                "color_mode": scene.render.image_settings.color_mode,
                "filepath": scene.render.filepath,
            }
        )
        # Blender 4.x only: save use_nodes (deprecated in 5.x)
        if bpy.app.version < (5, 0, 0):
            self._saved["use_nodes"] = scene.use_nodes

        try:
            self._saved["ffmpeg_codec"] = scene.render.ffmpeg.codec
            self._saved["ffmpeg_format"] = scene.render.ffmpeg.format
        except AttributeError:
            pass

        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        self._tmp_dir = tempfile.mkdtemp(prefix="fal_depth_video_")
        self._output_path = os.path.join(self._tmp_dir, "depth")

        scene.render.engine = get_eevee_engine()
        scene.render.film_transparent = False
        scene.render.use_compositing = True

        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        view_layer.use_pass_mist = True

        if camera and world:
            near, far = calc_scene_depth_bounds(scene, camera)
            if near is not None and far is not None:
                padding = (far - near) * 0.05
                world.mist_settings.start = max(0.0, near - padding)
                world.mist_settings.depth = (far - near) + padding * 2
                world.mist_settings.falloff = "LINEAR"
                print(f"fal.ai: Depth video range: {near:.2f} — {far:.2f}m")
            else:
                cam_data = camera.data
                world.mist_settings.start = cam_data.clip_start
                world.mist_settings.depth = cam_data.clip_end - cam_data.clip_start
                world.mist_settings.falloff = "LINEAR"

        tree = ensure_compositor_enabled(scene)
        self._saved_compositor = snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        rl_node = tree.nodes.new("CompositorNodeRLayers")
        rl_node.location = (0, 0)
        invert_node = tree.nodes.new("CompositorNodeInvert")
        invert_node.location = (300, 0)
        composite_node = tree.nodes.new("CompositorNodeComposite")
        composite_node.location = (600, 0)
        tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
        tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.image_settings.color_mode = "BW"
        scene.render.filepath = self._output_path

    def _finish_depth_animation(self, context: bpy.types.Context) -> None:
        """Upload the rendered depth video and submit the fal.ai generation job."""
        result_path = self._output_path + ".mp4"
        if not os.path.exists(result_path) and self._tmp_dir:
            for f in os.listdir(self._tmp_dir):
                if f.endswith(".mp4"):
                    result_path = os.path.join(self._tmp_dir, f)
                    break

        if not os.path.exists(result_path):
            self._restore_state(context)
            self.report({"ERROR"}, f"Depth video not found at {result_path}")
            return

        print(f"fal.ai: Depth video saved to {result_path}")

        self._restore_state(context)

        video_url = upload_file(result_path)
        params = self._model.parameters(
            prompt=self._prompt,
            enable_prompt_expansion=self._expand_prompt,
            video_url=video_url,
            num_frames=self._num_frames,
            image_url=self._first_frame_url,
            resolution=self._resolution,
        )

        def on_complete(job: FalJob) -> None:
            _handle_video_result(job)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Depth Video: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Depth rendered — generating video...")

    def _restore_state(self, context: bpy.types.Context) -> None:
        """Restore all scene render settings saved before the depth render."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        s = self._saved

        tree = get_compositor_node_tree(scene)
        if self._saved_compositor and tree:
            for node in tree.nodes:
                tree.nodes.remove(node)
            restore_compositor(tree, self._saved_compositor)
            self._saved_compositor = []

        if "engine" in s:
            scene.render.engine = s["engine"]
        if "film_transparent" in s:
            scene.render.film_transparent = s["film_transparent"]
        if "use_compositing" in s:
            scene.render.use_compositing = s["use_compositing"]
        # Blender 4.x only: restore use_nodes (deprecated in 5.x)
        if "use_nodes" in s and bpy.app.version < (5, 0, 0):
            scene.use_nodes = s["use_nodes"]
        if "use_pass_mist" in s:
            view_layer.use_pass_mist = s["use_pass_mist"]
        if "view_transform" in s:
            scene.view_settings.view_transform = s["view_transform"]
        if "look" in s:
            scene.view_settings.look = s["look"]
        if "file_format" in s:
            scene.render.image_settings.file_format = s["file_format"]
        if "color_mode" in s:
            scene.render.image_settings.color_mode = s["color_mode"]
        if "filepath" in s:
            scene.render.filepath = s["filepath"]

        try:
            if "ffmpeg_codec" in s:
                scene.render.ffmpeg.codec = s["ffmpeg_codec"]
            if "ffmpeg_format" in s:
                scene.render.ffmpeg.format = s["ffmpeg_format"]
        except AttributeError:
            pass

        if world:
            if "mist_start" in s:
                world.mist_settings.start = s["mist_start"]
            if "mist_depth" in s:
                world.mist_settings.depth = s["mist_depth"]

        self._saved.clear()

    def _capture_first_frame(self) -> str | None:
        """Capture the first-frame image before depth render overwrites state."""
        try:
            if self._first_frame_source == "FILE":
                if not self._first_frame_path.strip():
                    return None
                return upload_file(self._first_frame_path)
            elif self._first_frame_source == "TEXTURE":
                img = bpy.data.images.get(self._first_frame_texture)
                if not img:
                    return None
                return upload_blender_image(img)
            else:  # RENDER
                render_img = bpy.data.images.get("Render Result")
                if not render_img:
                    print("fal.ai: No render result available for first frame")
                    return None
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="fal_first_frame_"
                )
                tmp.close()
                render_img.save_render(tmp.name)
                print(f"fal.ai: First frame captured to {tmp.name}")
                return upload_file(tmp.name)
        except Exception as e:
            print(f"fal.ai: Failed to capture first frame: {e}")
            return None


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_video_result(job: FalJob) -> None:
    """Download video result and import to VSE."""
    if job.status == "error":
        print(f"fal.ai: Video generation failed: {job.error}")
        return

    result = job.result or {}
    video_url = None
    for key in ["video", "output", "video_url"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            video_url = val["url"]
            break
        elif isinstance(val, str) and val.startswith("http"):
            video_url = val
            break

    if not video_url:
        print("fal.ai: No video in response")
        return

    local_path = download_file(video_url, suffix=".mp4")
    add_video_to_vse(local_path, name="fal_video")
    print("fal.ai: Video imported to VSE!")
