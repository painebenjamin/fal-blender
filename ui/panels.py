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
            ("RENDER", "Render", "Neural rendering", "RENDER_RESULT", 2),
            ("VIDEO", "Video", "AI video generation", "FILE_MOVIE", 3),
            ("UPSCALE", "Upscale", "AI upscaling", "FULLSCREEN_ENTER", 4),
            ("AUDIO", "Audio", "Audio generation", "SOUND", 5),
            ("MESHOPS", "Mesh Ops", "3D-to-3D operations", "MOD_REMESH", 6),
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
        row.prop(fal, "active_tab")


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
# Upscale Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_upscale_panel(bpy.types.Panel):
    bl_label = "AI Upscale"
    bl_idname = "FAL_PT_upscale_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "UPSCALE"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_upscale

        layout.prop(props, "mode")

        if props.mode == "IMAGE":
            layout.prop(props, "image_endpoint")
        else:
            layout.prop(props, "video_endpoint")

        layout.prop(props, "source")
        if props.source == "FILE":
            layout.prop(props, "image_path")
        elif props.source == "TEXTURE":
            layout.prop_search(props, "texture_name", bpy.data, "images")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.upscale", icon="FULLSCREEN_ENTER")


# ---------------------------------------------------------------------------
# Neural Render Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_neural_render_panel(bpy.types.Panel):
    bl_label = "Neural Render"
    bl_idname = "FAL_PT_neural_render_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "RENDER"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_neural_render

        layout.prop(props, "mode")

        if props.mode == "DEPTH":
            layout.prop(props, "depth_endpoint")
        else:
            layout.prop(props, "sketch_endpoint")
            row = layout.row()
        row.prop(props, "enable_labels")
        sub = row.row()
        sub.enabled = props.enable_labels
        sub.prop(props, "auto_label")

        layout.prop(props, "prompt")

        layout.prop(props, "use_scene_resolution")
        if not props.use_scene_resolution:
            row = layout.row(align=True)
            row.prop(props, "width")
            row.prop(props, "height")
        else:
            scene = context.scene
            scale = scene.render.resolution_percentage / 100.0
            w = int(scene.render.resolution_x * scale)
            h = int(scene.render.resolution_y * scale)
            layout.label(text=f"Scene: {w} × {h} px")

        layout.prop(props, "seed")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.neural_render", icon="RENDER_RESULT")

# ---------------------------------------------------------------------------
# Video Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_video_panel(bpy.types.Panel):
    bl_label = "AI Video"
    bl_idname = "FAL_PT_video_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "VIDEO"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_video

        layout.prop(props, "mode")

        if props.mode == "TEXT":
            layout.prop(props, "text_endpoint")
            layout.prop(props, "prompt")
        elif props.mode == "IMAGE":
            layout.prop(props, "image_endpoint")
            layout.prop(props, "prompt")
            layout.prop(props, "image_source")
            if props.image_source == "FILE":
                layout.prop(props, "image_path")
        else:  # DEPTH
            layout.prop(props, "depth_endpoint")
            layout.prop(props, "prompt")
            layout.prop(props, "use_scene_resolution")

        # Duration
        layout.prop(props, "use_scene_duration")
        if props.use_scene_duration:
            scene = context.scene
            fps = scene.render.fps / scene.render.fps_base
            frames = scene.frame_end - scene.frame_start + 1
            dur = frames / fps
            layout.label(text=f"Scene: {dur:.1f}s ({frames} frames @ {fps:.0f} fps)")
        else:
            layout.prop(props, "duration")

        if props.mode == "DEPTH" and not context.scene.camera:
            layout.label(text="⚠ No camera in scene", icon="ERROR")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.generate_video", icon="FILE_MOVIE")


# ---------------------------------------------------------------------------
# Audio Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_audio_panel(bpy.types.Panel):
    bl_label = "Audio"
    bl_idname = "FAL_PT_audio_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "AUDIO"

    def draw(self, context: bpy.types.Context) -> None:
        from ..operators.audio import _draw_audio_panel
        props = context.scene.fal_audio
        _draw_audio_panel(self.layout, props)


# ---------------------------------------------------------------------------
# Mesh Ops Sub-Panel
# ---------------------------------------------------------------------------
class FAL_PT_mesh_ops_panel(bpy.types.Panel):
    bl_label = "Mesh Operations"
    bl_idname = "FAL_PT_mesh_ops_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = "FAL_PT_main_panel"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.fal.active_tab == "MESHOPS"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.fal_mesh_ops

        layout.prop(props, "mode")

        if props.mode == "RETEXTURE":
            layout.prop(props, "retexture_endpoint")
            layout.prop(props, "prompt")
        else:
            layout.prop(props, "remesh_endpoint")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("fal.mesh_ops", icon="MOD_REMESH")


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
            if job.status == "error":
                row.label(text=job.label, icon="ERROR")
            else:
                row.label(text=job.label, icon="TIME")
                row.label(text=job.status)
            if job.request_id:
                box.label(text=f"Request: {job.request_id}")
            if job.error:
                _draw_error(box, job.error)
            elif job.progress_message:
                box.label(text=job.progress_message)

        # Recent history
        if mgr.history:
            layout.separator()
            layout.label(text="Recent:", icon="TIME")
            for job in reversed(mgr.history[-5:]):
                box = layout.box()
                row = box.row()
                icon = "CHECKMARK" if job.status == "complete" else "ERROR"
                row.label(text=job.label, icon=icon)
                if job.request_id:
                    box.label(text=f"Request: {job.request_id}")
                if job.error:
                    _draw_error(box, job.error)


def _draw_error(layout, error_text: str):
    """Draw a word-wrapped error message in the panel."""
    col = layout.column(align=True)
    # Split on structured delimiters
    parts = error_text.split(" — ")
    for part in parts:
        while len(part) > 55:
            col.label(text=part[:55], icon="BLANK1")
            part = part[55:]
        if part.strip():
            col.label(text=part, icon="BLANK1")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalSceneProperties,
    FAL_PT_main_panel,
    FAL_PT_texture_panel,
    FAL_PT_gen3d_panel,
    FAL_PT_upscale_panel,
    FAL_PT_neural_render_panel,
    FAL_PT_video_panel,
    FAL_PT_audio_panel,
    FAL_PT_mesh_ops_panel,
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
