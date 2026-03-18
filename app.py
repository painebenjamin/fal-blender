import bpy

from .controllers import FalController
from .job_queue import JobManager

ALL_CONTROLLERS = FalController.enumerate()

if not ALL_CONTROLLERS:
    raise RuntimeError("No controllers found!")

print(f"ALL_CONTROLLERS: {ALL_CONTROLLERS}")

# ---------------------------------------------------------------------------
# Scene properties for UI state
# ---------------------------------------------------------------------------
class FalAISceneProperties(bpy.types.PropertyGroup):
    """Per-scene properties for fal.ai UI state."""

    # Active tab
    active_controller: bpy.props.EnumProperty(
        name="Tab",
        items=ALL_CONTROLLERS,
        default=ALL_CONTROLLERS[0][0],
    )


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------
class FAL_PT_MainPanel(bpy.types.Panel):
    bl_label = "fal.ai"
    bl_idname = "FAL_PT_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        fal = scene.fal

        # Tab row
        row = layout.row(align=True)
        row.prop(fal, "active_controller")


# ---------------------------------------------------------------------------
# Jobs Panel (always visible)
# ---------------------------------------------------------------------------
def _draw_error(layout: bpy.types.UILayout, error_text: str) -> None:
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

class FAL_PT_JobsPanel(bpy.types.Panel):
    bl_label = "Active Jobs"
    bl_idname = "FAL_PT_JobsPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = FAL_PT_MainPanel.bl_idname
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

# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
def register() -> None:
    bpy.utils.register_class(FalAISceneProperties)
    bpy.types.Scene.fal = bpy.props.PointerProperty(type=FalAISceneProperties)
    bpy.utils.register_class(FAL_PT_MainPanel)
    FalController.register_all(
        parent_id=FAL_PT_MainPanel.bl_idname,
    )
    bpy.utils.register_class(FAL_PT_JobsPanel)

def unregister() -> None:
    bpy.utils.unregister_class(FalAISceneProperties)
    if hasattr(bpy.types.Scene, "fal"):
        del bpy.types.Scene.fal
    bpy.utils.unregister_class(FAL_PT_MainPanel)
    FalController.unregister_all()
    bpy.utils.unregister_class(FAL_PT_JobsPanel)
    JobManager.reset()