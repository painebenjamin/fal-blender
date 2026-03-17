# SPDX-License-Identifier: Apache-2.0
"""AI Upscale operators — image and video upscaling via fal.ai."""

from __future__ import annotations

import tempfile

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    UPSCALE_IMAGE_ENDPOINTS,
    UPSCALE_VIDEO_ENDPOINTS,
    endpoint_items,
)
from ..core.api import download_file, upload_image_file
from ..core.job_queue import FalJob, JobManager


# ---------------------------------------------------------------------------
# Scene properties for upscale
# ---------------------------------------------------------------------------
class FalUpscaleProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("IMAGE", "Image", "Upscale an image"),
            ("VIDEO", "Video", "Upscale a video"),
        ],
        default="IMAGE",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(UPSCALE_IMAGE_ENDPOINTS),
        description="Which model to use for image upscaling",
    )

    video_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(UPSCALE_VIDEO_ENDPOINTS),
        description="Which model to use for video upscaling",
    )

    source: bpy.props.EnumProperty(
        name="Source",
        items=[
            ("FILE", "File", "Load from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
            ("TEXTURE", "Texture", "Use a texture from the blend file"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="File",
        description="Path to source image or video",
        subtype="FILE_PATH",
        default="",
    )

    texture_name: bpy.props.StringProperty(
        name="Texture",
        description="Name of the Blender image datablock to upscale",
        default="",
    )


# ---------------------------------------------------------------------------
# Result helpers (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _find_result_url(result: dict, is_video: bool) -> str | None:
    for key in ["video", "output", "image"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            return val["url"]
        elif isinstance(val, str) and val.startswith("http"):
            return val
    if "images" in result and result["images"]:
        first = result["images"][0]
        if isinstance(first, dict) and "url" in first:
            return first["url"]
        elif isinstance(first, str):
            return first
    return None


def _import_upscaled_image(local_path: str):
    img = bpy.data.images.load(local_path)
    img.name = "fal_upscaled"
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = img
                break


def _add_video_to_vse(local_path: str):
    scene = bpy.context.scene
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    se = scene.sequence_editor
    channel = 1
    used = {s.channel for s in se.sequences_all} if se.sequences_all else set()
    while channel in used:
        channel += 1
    se.sequences.new_movie(
        name="fal_upscaled",
        filepath=local_path,
        channel=channel,
        frame_start=scene.frame_current,
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_upscale(bpy.types.Operator):
    bl_idname = "fal.upscale"
    bl_label = "AI Upscale"
    bl_description = "Upscale an image or video using fal.ai"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_upscale
        if props.source == "FILE":
            return bool(props.image_path.strip())
        elif props.source == "RENDER":
            return bpy.data.images.get("Render Result") is not None
        elif props.source == "TEXTURE":
            return bool(props.texture_name.strip())
        return False

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_upscale
        is_video = props.mode == "VIDEO"

        # Resolve source to a file URL
        try:
            file_url = self._get_source_url(props)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        endpoint = props.video_endpoint if is_video else props.image_endpoint
        url_key = "video_url" if is_video else "image_url"
        args = {url_key: file_url}

        mode_str = props.mode.lower()

        def on_complete(job: FalJob):
            if job.status == "error":
                print(f"fal.ai: Upscale failed: {job.error}")
                return

            result = job.result or {}
            result_url = _find_result_url(result, is_video)
            if not result_url:
                print("fal.ai: No output in upscale response")
                return

            suffix = ".mp4" if is_video else ".png"
            local_path = download_file(result_url, suffix=suffix)

            if is_video:
                _add_video_to_vse(local_path)
                print("fal.ai: Upscaled video added to VSE")
            else:
                _import_upscaled_image(local_path)
                print("fal.ai: Upscaled image loaded")

        job = FalJob(
            endpoint=endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Upscale ({mode_str})",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Upscaling {mode_str}...")
        return {"FINISHED"}

    def _get_source_url(self, props) -> str:
        """Resolve the source to a fal CDN URL."""
        if props.source == "FILE":
            return upload_image_file(bpy.path.abspath(props.image_path))
        elif props.source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                raise RuntimeError("No render result available")
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            return upload_image_file(tmp.name)
        elif props.source == "TEXTURE":
            img = bpy.data.images.get(props.texture_name)
            if not img:
                raise RuntimeError(f"Texture '{props.texture_name}' not found")
            from ..core.api import upload_blender_image
            return upload_blender_image(img)
        raise RuntimeError("Unknown source type")








# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalUpscaleProperties,
    FAL_OT_upscale,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_upscale = bpy.props.PointerProperty(
        type=FalUpscaleProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_upscale"):
        del bpy.types.Scene.fal_upscale
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
