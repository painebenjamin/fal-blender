from __future__ import annotations

import tempfile

import bpy

from ...importers import import_glb
from ...job_queue import FalJob, JobManager
from ...models import ImageTo3DModel, TextTo3DModel
from ...utils import download_file, upload_file
from ..operators import FalOperator

TEXT_TO_3D_MODELS = TextTo3DModel.catalog()
IMAGE_TO_3D_MODELS = ImageTo3DModel.catalog()


def _handle_3d_result(job: FalJob, name: str) -> None:
    """Download GLB result and import into the scene."""
    if job.status == "error":
        print(f"fal.ai: 3D generation failed: {job.error}")
        return

    result = job.result or {}
    model_url = None

    for key in ["model_glb", "model_mesh", "model", "output", "mesh", "glb"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            model_url = val["url"]
            break
        elif isinstance(val, str) and val.startswith("http"):
            model_url = val
            break

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
        print(f"fal.ai: No 3D model URL found in response keys: {list(result.keys())}")
        return

    local_path = download_file(model_url, suffix=".glb")
    cursor_loc = tuple(bpy.context.scene.cursor.location)
    objects = import_glb(local_path, name=f"fal_{name}", location=cursor_loc)
    print(f"fal.ai: Imported {len(objects)} object(s) from 3D generation")


class FalGenerate3DOperator(FalOperator):
    label = "Generate 3D Model"
    description = "Generate a 3D model using fal.ai"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        else:
            return bool(props.image_path.strip() or props.image_source == "RENDER")

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        if props.mode == "TEXT":
            return self._text_to_3d(context, props)
        else:
            return self._image_to_3d(context, props)

    def _text_to_3d(self, context, props) -> set[str]:
        model = TEXT_TO_3D_MODELS[props.text_endpoint]
        params = model.parameters(
            prompt=props.prompt,
            enable_prompt_expansion=props.enable_prompt_expansion,
        )
        name = props.prompt[:30]

        def on_complete(job: FalJob):
            _handle_3d_result(job, name)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"3D: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model...")
        return {"FINISHED"}

    def _image_to_3d(self, context, props) -> set[str]:
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

        model = IMAGE_TO_3D_MODELS[props.image_endpoint]
        params = model.parameters(image_url=image_url)

        def on_complete(job: FalJob):
            _handle_3d_result(job, "image_model")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label="3D from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model from image...")
        return {"FINISHED"}
