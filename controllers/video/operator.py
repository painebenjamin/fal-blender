from __future__ import annotations

import tempfile
from typing import Any

import bpy

from ...importers import add_video_to_vse
from ...job_queue import FalJob, JobManager
from ...models import ImageToVideoModel, TextToVideoModel
from ...utils import (
    download_file,
    upload_file,
)
from ..operators import FalOperator

TEXT_TO_VIDEO_MODELS = TextToVideoModel.catalog()
IMAGE_TO_VIDEO_MODELS = ImageToVideoModel.catalog()


def _get_scene_duration(scene: bpy.types.Scene) -> float:
    """Calculate the scene duration in seconds from frame range and FPS."""
    fps = scene.render.fps / scene.render.fps_base
    frames = scene.frame_end - scene.frame_start + 1
    return frames / fps


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
        params = self.with_advanced_params(params, props)

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
            if not render_img or not render_img.has_data:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            try:
                render_img.save_render(tmp.name)
            except RuntimeError as e:
                self.report({"ERROR"}, f"Failed to save render: {e}")
                return {"CANCELLED"}
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
        params = self.with_advanced_params(params, props)

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
