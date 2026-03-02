# SPDX-License-Identifier: Apache-2.0
"""AI Video generation operators — text-to-video, image-to-video, depth video."""

from __future__ import annotations

import tempfile

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TEXT_TO_VIDEO_ENDPOINTS,
    IMAGE_TO_VIDEO_ENDPOINTS,
    DEPTH_VIDEO_ENDPOINTS,
    endpoint_items,
)
from ..core.job_queue import FalJob, JobManager
from ..core.api import download_file, upload_image_file


# ---------------------------------------------------------------------------
# Scene properties for video generation
# ---------------------------------------------------------------------------
class FalVideoProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-Video", "Generate video from text prompt"),
            ("IMAGE", "Image-to-Video", "Generate video from an image"),
            ("DEPTH", "Depth Video", "Depth-conditioned video generation"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(TEXT_TO_VIDEO_ENDPOINTS),
        description="Which model to use for text-to-video",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(IMAGE_TO_VIDEO_ENDPOINTS),
        description="Which model to use for image-to-video",
    )

    depth_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(DEPTH_VIDEO_ENDPOINTS),
        description="Which model to use for depth video",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the video you want to generate",
        default="",
    )

    duration: bpy.props.EnumProperty(
        name="Duration",
        items=[
            ("5", "5 seconds", ""),
            ("10", "10 seconds", ""),
        ],
        default="5",
    )

    image_source: bpy.props.EnumProperty(
        name="Image Source",
        items=[
            ("FILE", "File", "Load image from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="Image",
        description="Path to the source image",
        subtype="FILE_PATH",
        default="",
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_video(bpy.types.Operator):
    bl_idname = "fal.generate_video"
    bl_label = "Generate Video"
    bl_description = "Generate a video using fal.ai"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_video
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        elif props.mode == "IMAGE":
            return bool(
                props.image_path.strip() or props.image_source == "RENDER"
            )
        else:  # DEPTH
            return bool(props.prompt.strip())

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_video

        if props.mode == "TEXT":
            return self._text_to_video(context, props)
        elif props.mode == "IMAGE":
            return self._image_to_video(context, props)
        else:
            return self._depth_video(context, props)

    def _text_to_video(self, context, props) -> set[str]:
        args = {
            "prompt": props.prompt,
            "duration": int(props.duration),
        }

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.text_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Video: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating video...")
        return {"FINISHED"}

    def _image_to_video(self, context, props) -> set[str]:
        if props.image_source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            image_url = upload_image_file(tmp.name)
        elif props.image_path:
            image_url = upload_image_file(bpy.path.abspath(props.image_path))
        else:
            self.report({"ERROR"}, "No image specified")
            return {"CANCELLED"}

        args = {
            "prompt": props.prompt,
            "image_url": image_url,
            "duration": int(props.duration),
        }

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.image_endpoint,
            arguments=args,
            on_complete=on_complete,
            label="Video from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating video from image...")
        return {"FINISHED"}

    def _depth_video(self, context, props) -> set[str]:
        # Render depth pass and upload
        view_layer = context.view_layer
        view_layer.use_pass_z = True

        bpy.ops.render.render()

        render_img = bpy.data.images.get("Render Result")
        if not render_img:
            self.report({"ERROR"}, "Render failed")
            return {"CANCELLED"}

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        render_img.save_render(tmp.name)
        depth_url = upload_image_file(tmp.name)

        args = {
            "prompt": props.prompt,
            "depth_image_url": depth_url,
            "duration": int(props.duration),
        }

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.depth_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Depth Video: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating depth-conditioned video...")
        return {"FINISHED"}

    def _handle_video_result(self, job: FalJob):
        """Download video result and import to VSE."""
        if job.status == "error":
            self.report({"ERROR"}, f"Video generation failed: {job.error}")
            return

        result = job.result or {}

        # Find video URL in result
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
            self.report({"ERROR"}, "No video in response")
            return

        local_path = download_file(video_url, suffix=".mp4")

        # Import to VSE
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        se = scene.sequence_editor
        channel = 1
        used_channels = (
            {s.channel for s in se.sequences_all}
            if se.sequences_all
            else set()
        )
        while channel in used_channels:
            channel += 1

        se.sequences.new_movie(
            name="fal_video",
            filepath=local_path,
            channel=channel,
            frame_start=scene.frame_current,
        )
        self.report({"INFO"}, "Video imported to VSE!")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalVideoProperties,
    FAL_OT_generate_video,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_video = bpy.props.PointerProperty(
        type=FalVideoProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_video"):
        del bpy.types.Scene.fal_video
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
