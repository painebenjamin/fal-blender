from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..operators import FalOperator
from ...importers import import_image_as_texture
from ...job_queue import FalJob, JobManager
from ...models import (
    MaterialGenerationModel,
    PBREstimationModel,
    TilingTextureModel,
)
from ...utils import download_file, upload_blender_image, upload_file

TILING_MODELS = TilingTextureModel.catalog()
PBR_MODELS = PBREstimationModel.catalog()
MATERIAL_MODELS = MaterialGenerationModel.catalog()

PBR_MAP_NAMES = ("basecolor", "normal", "roughness", "metalness", "height")
PBR_DOWNLOAD_KEYS = [f"{name}.url" for name in PBR_MAP_NAMES]


class FalMaterialOperator(FalOperator):
    label = "Generate Material"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        if props.mode in ("FULL", "TILING_ONLY"):
            return bool(props.prompt.strip())
        if props.image_source == "FILE":
            return bool(props.image_path.strip())
        return bool(props.texture_name.strip())

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        if props.mode == "FULL":
            return self._full_pipeline(context, props)
        elif props.mode == "PBR_ONLY":
            return self._pbr_only(context, props)
        return self._tiling_only(context, props)

    # ── Full Pipeline ──────────────────────────────────────────────────

    def _full_pipeline(self, context, props) -> set[str]:
        model = MATERIAL_MODELS[props.full_endpoint]
        seed = props.seed if props.seed >= 0 else None
        params = model.parameters(
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            enable_prompt_expansion=props.enable_prompt_expansion,
            output_format=props.output_format,
            tiling_mode=props.tiling_mode,
        )

        target_obj_name = (
            context.active_object.name if context.active_object else None
        )
        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            _handle_pbr_result(job, target_obj_name, f"fal_{prompt_short}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=PBR_DOWNLOAD_KEYS,
            label=f"Material: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating material...")
        return {"FINISHED"}

    # ── PBR Only ───────────────────────────────────────────────────────

    def _pbr_only(self, context, props) -> set[str]:
        if props.image_source == "FILE":
            image_path = props.image_path
        else:
            img = bpy.data.images.get(props.texture_name)
            if not img:
                self.report({"ERROR"}, f"Image '{props.texture_name}' not found")
                return {"CANCELLED"}
            image_path = img.filepath_raw

        model = PBR_MODELS[props.pbr_endpoint]
        params = model.parameters(
            image_path=image_path,
            output_format=props.output_format,
        )

        target_obj_name = (
            context.active_object.name if context.active_object else None
        )
        label = props.texture_name[:20] or "pbr"

        def on_complete(job: FalJob):
            _handle_pbr_result(job, target_obj_name, f"fal_{label}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=PBR_DOWNLOAD_KEYS,
            label=f"PBR: {label}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Estimating PBR maps...")
        return {"FINISHED"}

    # ── Tiling Only ────────────────────────────────────────────────────

    def _tiling_only(self, context, props) -> set[str]:
        model = TILING_MODELS[props.tiling_endpoint]
        seed = props.seed if props.seed >= 0 else None
        params = model.parameters(
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            enable_prompt_expansion=props.enable_prompt_expansion,
            output_format=props.output_format,
            tiling_mode=props.tiling_mode,
        )

        target_obj_name = (
            context.active_object.name if context.active_object else None
        )
        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            _handle_tiling_result(job, target_obj_name, f"fal_{prompt_short}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=["images.0.url"],
            label=f"Tiling: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating tileable texture...")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Result handlers (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_pbr_result(
    job: FalJob,
    target_obj_name: str | None,
    name: str,
) -> None:
    if job.status == "error":
        print(f"fal.ai: PBR generation failed: {job.error}")
        return

    paths: dict[str, str] = {}
    for map_name in PBR_MAP_NAMES:
        local_path = job.downloaded_files.get(f"{map_name}.url")
        if local_path:
            paths[map_name] = local_path

    required = {"basecolor", "normal", "roughness", "metalness"}
    missing = required - paths.keys()
    if missing:
        print(f"fal.ai: Missing PBR maps in response: {missing}")
        return

    obj = bpy.data.objects.get(target_obj_name) if target_obj_name else None
    if not obj:
        print("fal.ai: No active object — PBR maps downloaded but not applied")
        return

    _apply_pbr_material(obj, paths, name)
    print("fal.ai: PBR material applied!")


def _handle_tiling_result(
    job: FalJob,
    target_obj_name: str | None,
    name: str,
) -> None:
    if job.status == "error":
        print(f"fal.ai: Tiling generation failed: {job.error}")
        return

    local_path = job.downloaded_files.get("images.0.url")
    if not local_path:
        result = job.result or {}
        image_url = None
        if "images" in result and result["images"]:
            image_url = result["images"][0].get("url")
        if not image_url:
            print("fal.ai: No image in tiling response")
            return
        local_path = download_file(image_url, suffix=".png")

    obj = bpy.data.objects.get(target_obj_name) if target_obj_name else None
    if obj:
        bpy.context.view_layer.objects.active = obj
    import_image_as_texture(local_path, name=name, apply_to_selected=obj is not None)
    print("fal.ai: Tiling texture applied!")


# ---------------------------------------------------------------------------
# Blender material builder
# ---------------------------------------------------------------------------
def _apply_pbr_material(
    obj: bpy.types.Object,
    paths: dict[str, str],
    name: str = "fal_pbr",
) -> bpy.types.Material:
    """Create a Principled BSDF material with full PBR map connections."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # Base Color
    tex_bc = nodes.new("ShaderNodeTexImage")
    tex_bc.location = (-400, 200)
    tex_bc.image = bpy.data.images.load(paths["basecolor"])
    tex_bc.image.name = f"{name}_basecolor"
    links.new(tex_bc.outputs["Color"], principled.inputs["Base Color"])

    # Normal Map
    tex_norm = nodes.new("ShaderNodeTexImage")
    tex_norm.location = (-700, -400)
    tex_norm.image = bpy.data.images.load(paths["normal"])
    tex_norm.image.name = f"{name}_normal"
    tex_norm.image.colorspace_settings.name = "Non-Color"
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.location = (-400, -400)
    links.new(tex_norm.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

    # Roughness
    tex_rough = nodes.new("ShaderNodeTexImage")
    tex_rough.location = (-400, -100)
    tex_rough.image = bpy.data.images.load(paths["roughness"])
    tex_rough.image.name = f"{name}_roughness"
    tex_rough.image.colorspace_settings.name = "Non-Color"
    links.new(tex_rough.outputs["Color"], principled.inputs["Roughness"])

    # Metalness
    tex_metal = nodes.new("ShaderNodeTexImage")
    tex_metal.location = (-400, -250)
    tex_metal.image = bpy.data.images.load(paths["metalness"])
    tex_metal.image.name = f"{name}_metalness"
    tex_metal.image.colorspace_settings.name = "Non-Color"
    links.new(tex_metal.outputs["Color"], principled.inputs["Metallic"])

    # Height → Displacement
    if "height" in paths:
        tex_height = nodes.new("ShaderNodeTexImage")
        tex_height.location = (-700, -600)
        tex_height.image = bpy.data.images.load(paths["height"])
        tex_height.image.name = f"{name}_height"
        tex_height.image.colorspace_settings.name = "Non-Color"

        disp = nodes.new("ShaderNodeDisplacement")
        disp.location = (0, -400)
        links.new(tex_height.outputs["Color"], disp.inputs["Height"])
        links.new(disp.outputs["Displacement"], output.inputs["Displacement"])
        mat.cycles.displacement_method = "BOTH"

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return mat
