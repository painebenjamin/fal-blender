from .controllers import FalController
from .job_queue import JobManager

ALL_CONTROLLERS = FalController.enumerate()

# ---------------------------------------------------------------------------
# Scene properties for UI state
# ---------------------------------------------------------------------------
class FalAISceneProperties(bpy.types.PropertyGroup):
    """Per-scene properties for fal.ai UI state."""

    # Active tab
    active_tab: bpy.props.EnumProperty(
        name="Tab",
        items=ALL_CONTROLLERS,
        default=ALL_CONTROLLERS[0][0],
    )


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------
class FalAIMainPanel(bpy.types.Panel):
    bl_label = "fal.ai"
    bl_idname = "FalAIMainPanel"
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
# Jobs Panel (always visible)
# ---------------------------------------------------------------------------
class FalAIJobsPanel(bpy.types.Panel):
    bl_label = "Active Jobs"
    bl_idname = "FalAIJobsPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_parent_id = FalAIMainPanel.bl_idname
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
    bpy.utils.register_class(FalAIMainPanel)
    bpy.utils.register_class(FalAIJobsPanel)
    bpy.types.Scene.fal = bpy.props.PointerProperty(type=FalAISceneProperties)
    FalController.register_all()

def unregister() -> None:
    bpy.utils.unregister_class(FalAISceneProperties)
    bpy.utils.unregister_class(FalAIMainPanel)
    bpy.utils.unregister_class(FalAIJobsPanel)
    if hasattr(bpy.types.Scene, "fal"):
        del bpy.types.Scene.fal
    FalController.unregister_all()
    JobManager.reset()