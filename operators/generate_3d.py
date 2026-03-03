# SPDX-License-Identifier: Apache-2.0
"""3D Generation operators — text-to-3D and image-to-3D."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TEXT_TO_3D_ENDPOINTS,
    IMAGE_TO_3D_ENDPOINTS,
    endpoint_items,
)
from ..core.job_queue import FalJob, JobManager
from ..core.importers import import_glb
from ..core.api import download_file, upload_image_file, upload_blender_image


# ---------------------------------------------------------------------------
# Scene properties for 3D generation
# ---------------------------------------------------------------------------
class FalGen3DProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-3D", "Generate 3D model from text prompt"),
            ("IMAGE", "Image-to-3D", "Generate 3D model from an image"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(TEXT_TO_3D_ENDPOINTS),
        description="Which model to use for text-to-3D",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(IMAGE_TO_3D_ENDPOINTS),
        description="Which model to use for image-to-3D",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the 3D model you want to generate",
        default="",
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
class FAL_OT_generate_3d(bpy.types.Operator):
    bl_idname = "fal.generate_3d"
    bl_label = "Generate 3D Model"
    bl_description = "Generate a 3D model using fal.ai"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_gen3d
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        else:
            return bool(
                props.image_path.strip()
                or props.image_source == "RENDER"
            )

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_gen3d

        if props.mode == "TEXT":
            return self._text_to_3d(context, props)
        else:
            return self._image_to_3d(context, props)

    def _text_to_3d(self, context, props) -> set[str]:
        args = {"prompt": props.prompt}
        label = f"3D: {props.prompt[:30]}"

        def on_complete(job: FalJob):
            self._handle_3d_result(job, props.prompt[:30])

        job = FalJob(
            endpoint=props.text_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=label,
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model...")
        return {"FINISHED"}

    def _image_to_3d(self, context, props) -> set[str]:
        # Get image URL
        if props.image_source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            # Save render to temp and upload
            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            image_url = upload_image_file(tmp.name)
        elif props.image_path:
            image_url = upload_image_file(bpy.path.abspath(props.image_path))
        else:
            self.report({"ERROR"}, "No image specified")
            return {"CANCELLED"}

        args = {"image_url": image_url}
        label = "3D from image"

        def on_complete(job: FalJob):
            self._handle_3d_result(job, "image_model")

        job = FalJob(
            endpoint=props.image_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=label,
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model from image...")
        return {"FINISHED"}

    def _handle_3d_result(self, job: FalJob, name: str):
        """Process 3D generation result — download GLB and import."""
        if job.status == "error":
            self.report({"ERROR"}, f"3D generation failed: {job.error}")
            return

        result = job.result or {}

        # Find GLB/model URL in result
        # Meshy v6 format: {"model_glb": {"url": "..."}, "model_urls": {"fbx": {"url": "..."}, ...}}
        model_url = None

        # Check top-level keys that contain {"url": "..."} objects
        for key in [
            "model_glb", "model_mesh", "model", "output", "mesh", "glb",
        ]:
            val = result.get(key)
            if isinstance(val, dict) and "url" in val:
                model_url = val["url"]
                break
            elif isinstance(val, str) and val.startswith("http"):
                model_url = val
                break

        # Check model_urls dict — Meshy nests format objects: {"glb": {"url": "..."}, "fbx": {"url": "..."}}
        if not model_url and "model_urls" in result:
            urls = result["model_urls"]
            if isinstance(urls, dict):
                for fmt in ("glb", "obj", "fbx", "usdz"):
                    fmt_val = urls.get(fmt)
                    if isinstance(fmt_val, dict) and "url" in fmt_val:
                        model_url = fmt_val["url"]
                        break
                    elif isinstance(fmt_val, str) and fmt_val.startswith("http"):
                        model_url = fmt_val
                        break

        if not model_url:
            print(f"fal.ai ERROR: No 3D model URL found in response keys: {list(result.keys())}")
            print(f"fal.ai ERROR: Full response: {result}")
            return

        # Download GLB
        local_path = download_file(model_url, suffix=".glb")

        # Import into scene
        cursor_loc = tuple(bpy.context.scene.cursor.location)
        objects = import_glb(
            local_path,
            name=f"fal_{name}",
            location=cursor_loc,
        )
        self.report(
            {"INFO"},
            f"Imported {len(objects)} object(s) from 3D generation",
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalGen3DProperties,
    FAL_OT_generate_3d,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_gen3d = bpy.props.PointerProperty(
        type=FalGen3DProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_gen3d"):
        del bpy.types.Scene.fal_gen3d
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
