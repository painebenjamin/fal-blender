# SPDX-License-Identifier: Apache-2.0
"""Text-to-Texture operator — generate image via fal, apply as material."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    IMAGE_GENERATION_ENDPOINTS,
    TILING_ENDPOINTS,
    endpoint_items,
)
from ..core.api import resolve_endpoint, build_image_gen_args
from ..core.job_queue import FalJob, JobManager
from ..core.importers import import_image_as_texture


# ---------------------------------------------------------------------------
# Scene properties for texture generation
# ---------------------------------------------------------------------------
class FalTextureProperties(bpy.types.PropertyGroup):
    endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(IMAGE_GENERATION_ENDPOINTS + TILING_ENDPOINTS),
        description="Which model to use for image generation",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the texture you want to generate",
        default="",
    )

    width: bpy.props.IntProperty(
        name="W",
        description="Output width in pixels",
        default=1024,
        min=64,
        max=4096,
        step=16,
    )

    height: bpy.props.IntProperty(
        name="H",
        description="Output height in pixels",
        default=1024,
        min=64,
        max=4096,
        step=16,
    )

    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed (-1 for random)",
        default=-1,
        min=-1,
        max=2147483647,
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_texture(bpy.types.Operator):
    bl_idname = "fal.generate_texture"
    bl_label = "Generate Texture"
    bl_description = "Generate a texture using fal.ai and apply to selected object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_texture
        return bool(props.prompt.strip())

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_texture

        seed = props.seed if props.seed >= 0 else None
        args = build_image_gen_args(
            endpoint_id=props.endpoint,
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
        )

        # Capture reference to target object
        target_obj_name = (
            context.active_object.name if context.active_object else None
        )
        requested_w = props.width
        requested_h = props.height

        def on_complete(job: FalJob):
            if job.status == "error":
                print(f"fal.ai: Generation failed: {job.error}")
                return

            # Find image URL in result
            result = job.result or {}
            image_url = None

            # Try common result shapes
            if "images" in result and result["images"]:
                image_url = result["images"][0].get("url")
            elif "image" in result:
                img = result["image"]
                image_url = img.get("url") if isinstance(img, dict) else img
            elif "output" in result:
                out = result["output"]
                if isinstance(out, dict) and "url" in out:
                    image_url = out["url"]

            if not image_url:
                print("fal.ai: No image in response")
                return

            # Download image
            from ..core.api import download_file

            local_path = download_file(image_url, suffix=".png")

            # Resize/crop to exact requested dimensions if needed
            try:
                _resize_to_exact(local_path, requested_w, requested_h)
            except Exception as e:
                print(f"fal.ai: resize warning: {e}")

            # Import as texture
            obj = (
                bpy.data.objects.get(target_obj_name)
                if target_obj_name
                else None
            )
            if obj:
                bpy.context.view_layer.objects.active = obj
            import_image_as_texture(
                local_path,
                name=f"fal_{props.prompt[:20]}",
                apply_to_selected=obj is not None,
            )
            print("fal.ai: Texture applied!")

        job = FalJob(
            endpoint=resolve_endpoint(props.endpoint, args),
            arguments=args,
            on_complete=on_complete,
            label=f"Texture: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating texture...")
        return {"FINISHED"}


def _resize_to_exact(filepath: str, target_w: int, target_h: int):
    """Resize/crop image to exact target dimensions if they don't match."""
    try:
        from PIL import Image
    except ImportError:
        return  # Pillow not available, skip resize

    img = Image.open(filepath)
    if img.size == (target_w, target_h):
        return

    # Resize to cover, then center crop
    iw, ih = img.size
    scale = max(target_w / iw, target_h / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    img.save(filepath)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalTextureProperties,
    FAL_OT_generate_texture,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_texture = bpy.props.PointerProperty(
        type=FalTextureProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_texture"):
        del bpy.types.Scene.fal_texture
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
