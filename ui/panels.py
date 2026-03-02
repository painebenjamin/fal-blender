# SPDX-License-Identifier: Apache-2.0
"""N-Panel sidebar UI for fal.ai in the 3D Viewport."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..core.job_queue import JobManager


# ---------------------------------------------------------------------------
# Scene properties for UI state
# ---------------------------------------------------------------------------
class FalSceneProperties(bpy.types.PropertyGroup):
    """Per-scene properties for fal.ai UI state."""

    # Active tab
    active_tab: bpy.props.EnumProperty(
        name="Tab",
        items=[
            ("TEXTURE", "Texture", "Text-to-Texture generation", "TEXTURE", 0),
            ("GEN3D", "3D", "3D model generation", "MESH_MONKEY", 1),
            # ("VECTOR", "Vector", "Vector/Curve generation", "GREASEPENCIL", 2),
            # ("RENDER", "Render", "Neural rendering", "RENDER_RESULT", 3),
            # ("VIDEO", "Video", "AI video generation", "FILE_MOVIE", 4),
            # ("UPSCALE", "Upscale", "AI upscaling", "FULLSCREEN_ENTER", 5),
            # ("AUDIO", "Audio", "Audio generation", "SOUND", 6),
        ],
        default="TEXTURE",
    )


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------
class FAL_PT_main_panel(bpy.types.Panel):
    bl_label = "fal.ai"
    bl_idname = "FAL_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        fal = scene.fal

        # Tab row
        row = layout.row(align=True)
        row.prop(fal, "active_tab", expand=True)


# ---------------------------------------------------------------------------
# Texture Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_texture_panel(bpy.types.Panel):
    bl_label = "Text-to-Texture"
    bl_idname = "FAL_PT_texture_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "TEXTURE"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_texture

        layout.prop(props, "endpoint")
        layout.prop(props, "prompt")

        row = layout.row(align=True)
        row.prop(props, "width")
        row.prop(props, "height")

        layout.prop(props, "seed")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.generate_texture", icon="TEXTURE")


# ---------------------------------------------------------------------------
# 3D Generation Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_gen3d_panel(bpy.types.Panel):
    bl_label = "3D Generation"
    bl_idname = "FAL_PT_gen3d_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "GEN3D"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_gen3d

        # Sub-mode: text-to-3d vs image-to-3d
        layout.prop(props, "mode")

        if props.mode == "TEXT":
            layout.prop(props, "text_endpoint")
            layout.prop(props, "prompt")
        else:
            layout.prop(props, "image_endpoint")
            layout.prop(props, "image_source")
            if props.image_source == "FILE":
                layout.prop(props, "image_path")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.generate_3d", icon="MESH_MONKEY")


# ---------------------------------------------------------------------------
# Jobs Panel (always visible)
# ---------------------------------------------------------------------------
class FAL_PT_jobs_panel(bpy.types.Panel):
    bl_label = "Active Jobs"
    bl_idname = "FAL_PT_jobs_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        mgr = JobManager.get()

        if not mgr.jobs and not mgr.history:
            layout.label(text="No active jobs", icon="INFO")
            return

        # Active jobs
        for job in mgr.active_jobs:
            box = layout.box()
            row = box.row()
            row.label(text=job.label, icon="TIME")
            row.label(text=job.status)
            if job.progress_message:
                box.label(text=job.progress_message)

        # Recent history
        if mgr.history:
            layout.separator()
            layout.label(text="Recent:", icon="TIME")
            for job in reversed(mgr.history[-5:]):
                row = layout.row()
                icon = "CHECKMARK" if job.status == "complete" else "ERROR"
                row.label(text=job.label, icon=icon)
                if job.error:
                    row.label(text=job.error[:40])


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalSceneProperties,
    FAL_PT_main_panel,
    FAL_PT_texture_panel,
    FAL_PT_gen3d_panel,
    FAL_PT_jobs_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal = bpy.props.PointerProperty(type=FalSceneProperties)


def unregister():
    if hasattr(bpy.types.Scene, "fal"):
        del bpy.types.Scene.fal
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
