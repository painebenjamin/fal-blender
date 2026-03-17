# SPDX-License-Identifier: Apache-2.0
"""PBR Material generation operator.

Three modes:
- FULL: Prompt -> tileable texture -> CHORD PBR maps -> Principled BSDF
- PBR_ONLY: Existing image -> CHORD PBR maps -> Principled BSDF
- TILING_ONLY: Prompt -> tileable texture (no PBR decomposition)
"""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TILING_ENDPOINTS,
    PBR_ENDPOINTS,
    endpoint_items,
)
from ..core.api import (
    build_image_gen_args,
    download_file,
    resolve_endpoint,
    upload_blender_image,
    upload_image_file,
)
from ..core.job_queue import FalJob, JobManager


# ---------------------------------------------------------------------------
# Scene properties
# ---------------------------------------------------------------------------
class FalMaterialProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("FULL", "Full Pipeline", "Generate tileable texture then extract PBR maps"),
            ("PBR_ONLY", "PBR from Image", "Extract PBR maps from an existing image"),
            ("TILING_ONLY", "Tiling Texture", "Generate a tileable texture only"),
        ],
        default="FULL",
    )

    tiling_endpoint: bpy.props.EnumProperty(
        name="Tiling Model",
        items=endpoint_items(TILING_ENDPOINTS),
        description="Model for seamless tiling texture generation",
    )

    pbr_endpoint: bpy.props.EnumProperty(
        name="PBR Model",
        items=endpoint_items(PBR_ENDPOINTS),
        description="Model for PBR material map estimation",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the material to generate",
        default="",
    )
    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt for better results",
        default=True,
    )


    width: bpy.props.IntProperty(
        name="W", default=1024, min=512, max=2048, step=16,
        description="Texture width in pixels",
    )

    height: bpy.props.IntProperty(
        name="H", default=1024, min=512, max=2048, step=16,
        description="Texture height in pixels",
    )

    tiling_mode: bpy.props.EnumProperty(
        name="Tiling",
        items=[
            ("both", "All Directions", "Seamless tiling in both directions"),
            ("horizontal", "Horizontal", "Tile left-right only (e.g. walls with baseboard)"),
            ("vertical", "Vertical", "Tile top-bottom only"),
        ],
        default="both",
        description="Which directions the texture should tile seamlessly",
    )

    seed: bpy.props.IntProperty(
        name="Seed", default=-1, min=-1, max=2147483647,
        description="Random seed (-1 for random)",
    )

    image_source: bpy.props.EnumProperty(
        name="Source",
        items=[
            ("FILE", "File", "Load from disk"),
            ("TEXTURE", "Blender Texture", "Use an existing Blender image"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="Image Path",
        subtype="FILE_PATH",
        description="Path to the input texture image",
    )

    texture_name: bpy.props.StringProperty(
        name="Texture",
        description="Blender image to use as input",
    )

    output_format: bpy.props.EnumProperty(
        name="Format",
        items=[
            ("png", "PNG", "Lossless"),
            ("jpeg", "JPEG", "Lossy, smaller"),
            ("webp", "WebP", "Modern format"),
        ],
        default="png",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _apply_pbr_material(
    obj: bpy.types.Object,
    basecolor_path: str,
    normal_path: str,
    roughness_path: str,
    metalness_path: str,
    name: str = "fal_pbr",
) -> bpy.types.Material:
    """Create a Principled BSDF material with full PBR map connections."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear defaults
    nodes.clear()

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    # Principled BSDF
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # Base Color
    tex_bc = nodes.new("ShaderNodeTexImage")
    tex_bc.location = (-400, 200)
    tex_bc.image = bpy.data.images.load(basecolor_path)
    tex_bc.image.name = f"{name}_basecolor"
    links.new(tex_bc.outputs["Color"], principled.inputs["Base Color"])

    # Normal Map
    tex_norm = nodes.new("ShaderNodeTexImage")
    tex_norm.location = (-700, -400)
    tex_norm.image = bpy.data.images.load(normal_path)
    tex_norm.image.name = f"{name}_normal"
    tex_norm.image.colorspace_settings.name = "Non-Color"

    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.location = (-400, -400)
    links.new(tex_norm.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

    # Roughness
    tex_rough = nodes.new("ShaderNodeTexImage")
    tex_rough.location = (-400, -100)
    tex_rough.image = bpy.data.images.load(roughness_path)
    tex_rough.image.name = f"{name}_roughness"
    tex_rough.image.colorspace_settings.name = "Non-Color"
    links.new(tex_rough.outputs["Color"], principled.inputs["Roughness"])

    # Metalness
    tex_metal = nodes.new("ShaderNodeTexImage")
    tex_metal.location = (-400, -250)
    tex_metal.image = bpy.data.images.load(metalness_path)
    tex_metal.image.name = f"{name}_metalness"
    tex_metal.image.colorspace_settings.name = "Non-Color"
    links.new(tex_metal.outputs["Color"], principled.inputs["Metallic"])

    # Apply to object
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return mat


def _apply_simple_texture(
    obj: bpy.types.Object,
    texture_path: str,
    name: str = "fal_tiling",
) -> None:
    """Apply a single texture as base color on the active object."""
    from ..core.importers import import_image_as_texture

    if obj:
        bpy.context.view_layer.objects.active = obj
    import_image_as_texture(
        texture_path,
        name=name,
        apply_to_selected=obj is not None,
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_material(bpy.types.Operator):
    bl_idname = "fal.generate_material"
    bl_label = "Generate Material"
    bl_description = "Generate PBR material maps using fal.ai"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_material
        if props.mode in ("FULL", "TILING_ONLY"):
            return bool(props.prompt.strip())
        else:
            # PBR_ONLY needs an image source
            if props.image_source == "FILE":
                return bool(props.image_path.strip())
            else:
                return bool(props.texture_name.strip())

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_material
        target_obj_name = (
            context.active_object.name if context.active_object else None
        )

        if props.mode == "FULL":
            self._run_full_pipeline(context, props, target_obj_name)
        elif props.mode == "PBR_ONLY":
            self._run_pbr_only(context, props, target_obj_name)
        else:  # TILING_ONLY
            self._run_tiling_only(context, props, target_obj_name)

        return {"FINISHED"}

    def _run_full_pipeline(self, context, props, target_obj_name):
        """Step 1: Generate tiling texture, Step 2: Run CHORD PBR on it."""
        seed = props.seed if props.seed >= 0 else None
        args = build_image_gen_args(
            endpoint_id=props.tiling_endpoint,
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            expand_prompt=props.enable_prompt_expansion,
            extra={"output_format": props.output_format, "tiling_mode": props.tiling_mode},
        )

        prompt_short = props.prompt[:20]
        pbr_endpoint = props.pbr_endpoint
        output_format = props.output_format

        def on_tiling_complete(job: FalJob):
            if job.status == "error":
                print(f"fal.ai: Tiling failed: {job.error}")
                return

            result = job.result or {}
            image_url = None
            if "images" in result and result["images"]:
                image_url = result["images"][0].get("url")

            if not image_url:
                print("fal.ai: No image in tiling response")
                return

            # Now run CHORD PBR on the generated texture
            pbr_args = {
                "image_url": image_url,
                "output_format": output_format,
            }

            def on_pbr_complete(pbr_job: FalJob):
                if pbr_job.status == "error":
                    print(f"fal.ai: PBR failed: {pbr_job.error}")
                    return

                pbr_result = pbr_job.result or {}
                _finish_pbr(
                    pbr_result, target_obj_name,
                    f"fal_{prompt_short}",
                )

            pbr_job = FalJob(
                endpoint=pbr_endpoint,
                arguments=pbr_args,
                on_complete=on_pbr_complete,
                label=f"PBR: {prompt_short}...",
            )
            JobManager.get().submit(pbr_job)

        job = FalJob(
            endpoint=resolve_endpoint(props.tiling_endpoint, args),
            arguments=args,
            on_complete=on_tiling_complete,
            label=f"Tiling: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating tileable material...")

    def _run_pbr_only(self, context, props, target_obj_name):
        """Run CHORD PBR on an existing image."""
        # Get image URL
        if props.image_source == "FILE":
            image_url = upload_image_file(props.image_path)
        else:
            img = bpy.data.images.get(props.texture_name)
            if not img:
                print(f"fal.ai: Image '{props.texture_name}' not found")
                return
            image_url = upload_blender_image(img)

        pbr_args = {
            "image_url": image_url,
            "output_format": props.output_format,
        }

        prompt_short = props.texture_name[:20] or "pbr"

        def on_pbr_complete(job: FalJob):
            if job.status == "error":
                print(f"fal.ai: PBR failed: {job.error}")
                return
            _finish_pbr(
                job.result or {}, target_obj_name,
                f"fal_{prompt_short}",
            )

        job = FalJob(
            endpoint=props.pbr_endpoint,
            arguments=pbr_args,
            on_complete=on_pbr_complete,
            label=f"PBR: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Estimating PBR maps...")

    def _run_tiling_only(self, context, props, target_obj_name):
        """Generate a tiling texture and apply as base color."""
        seed = props.seed if props.seed >= 0 else None
        args = build_image_gen_args(
            endpoint_id=props.tiling_endpoint,
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            expand_prompt=props.enable_prompt_expansion,
            extra={"output_format": props.output_format, "tiling_mode": props.tiling_mode},
        )

        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            if job.status == "error":
                print(f"fal.ai: Tiling failed: {job.error}")
                return

            result = job.result or {}
            image_url = None
            if "images" in result and result["images"]:
                image_url = result["images"][0].get("url")

            if not image_url:
                print("fal.ai: No image in response")
                return

            local_path = download_file(image_url, suffix=".png")
            obj = (
                bpy.data.objects.get(target_obj_name)
                if target_obj_name else None
            )
            _apply_simple_texture(obj, local_path, f"fal_{prompt_short}")
            print("fal.ai: Tiling texture applied!")

        job = FalJob(
            endpoint=resolve_endpoint(props.tiling_endpoint, args),
            arguments=args,
            on_complete=on_complete,
            label=f"Tiling: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating tileable texture...")


def _finish_pbr(
    result: dict,
    target_obj_name: str | None,
    name: str,
):
    """Download PBR maps and apply as Principled BSDF material."""
    map_urls = {}
    for map_name in ("basecolor", "normal", "roughness", "metalness"):
        entry = result.get(map_name, {})
        url = entry.get("url") if isinstance(entry, dict) else None
        if not url:
            print(f"fal.ai: Missing {map_name} map in response")
            return
        map_urls[map_name] = url

    # Download all maps
    local_paths = {}
    for map_name, url in map_urls.items():
        local_paths[map_name] = download_file(url, suffix=".png")

    obj = (
        bpy.data.objects.get(target_obj_name)
        if target_obj_name else None
    )
    if not obj:
        print("fal.ai: No active object — PBR maps downloaded but not applied")
        return

    _apply_pbr_material(
        obj,
        basecolor_path=local_paths["basecolor"],
        normal_path=local_paths["normal"],
        roughness_path=local_paths["roughness"],
        metalness_path=local_paths["metalness"],
        name=name,
    )
    print("fal.ai: PBR material applied!")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalMaterialProperties,
    FAL_OT_generate_material,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_material = bpy.props.PointerProperty(
        type=FalMaterialProperties,
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_material"):
        del bpy.types.Scene.fal_material
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
