# SPDX-License-Identifier: Apache-2.0
"""3D-to-3D operators — retexture and remesh."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    RETEXTURE_ENDPOINTS,
    REMESH_ENDPOINTS,
    endpoint_items,
)
from ..core.job_queue import FalJob, JobManager
from ..core.api import download_file, upload_mesh_as_glb
from ..core.importers import import_glb


# ---------------------------------------------------------------------------
# Scene properties for mesh operations
# ---------------------------------------------------------------------------
class FalMeshOpsProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("RETEXTURE", "Retexture", "Re-texture a mesh with AI"),
            ("REMESH", "Remesh", "Remesh a model with AI"),
        ],
        default="RETEXTURE",
    )

    retexture_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(RETEXTURE_ENDPOINTS),
        description="Which model to use for retexturing",
    )

    remesh_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(REMESH_ENDPOINTS),
        description="Which model to use for remeshing",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the desired texture/style (retexture only)
    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt for better results",
        default=True,
    )
",
        default="",
    )


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_mesh_result(job: FalJob, original_name: str):
    """Download result GLB and import."""
    if job.status == "error":
        print(f"fal.ai: Mesh operation failed: {job.error}")
        return

    result = job.result or {}
    model_url = None
    for key in ["model_mesh", "model", "output", "mesh", "glb"]:
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
            model_url = urls.get("glb") or urls.get("obj")
        elif isinstance(urls, list) and urls:
            model_url = urls[0]

    if not model_url:
        print("fal.ai: No model in response")
        return

    local_path = download_file(model_url, suffix=".glb")
    cursor_loc = tuple(bpy.context.scene.cursor.location)
    objects = import_glb(local_path, name=f"fal_{original_name}", location=cursor_loc)
    print(f"fal.ai: Imported {len(objects)} object(s) from mesh operation")


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_mesh_ops(bpy.types.Operator):
    bl_idname = "fal.mesh_ops"
    bl_label = "Process Mesh"
    bl_description = "Retexture or remesh selected object using fal.ai"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        if not obj or obj.type != "MESH":
            return False
        props = context.scene.fal_mesh_ops
        if props.mode == "RETEXTURE":
            return bool(props.prompt.strip())
        return True  # REMESH doesn't need a prompt

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_mesh_ops
        obj = context.active_object

        # Upload mesh
        mesh_url = upload_mesh_as_glb(obj)
        obj_name = obj.name

        if props.mode == "RETEXTURE":
            endpoint = props.retexture_endpoint
            args = {
                "model_url": mesh_url,
                "prompt": props.prompt,
                "expand_prompt": props.enable_prompt_expansion,
            }
            label = f"Retexture: {props.prompt[:30]}"
        else:
            endpoint = props.remesh_endpoint
            args = {
                "model_url": mesh_url,
            }
            label = f"Remesh: {obj_name}"

        def on_complete(job: FalJob):
            _handle_mesh_result(job, obj_name)

        job = FalJob(
            endpoint=endpoint,
            arguments=args,
            on_complete=on_complete,
            label=label,
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Processing mesh ({props.mode.lower()})...")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalMeshOpsProperties,
    FAL_OT_mesh_ops,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_mesh_ops = bpy.props.PointerProperty(
        type=FalMeshOpsProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_mesh_ops"):
        del bpy.types.Scene.fal_mesh_ops
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
