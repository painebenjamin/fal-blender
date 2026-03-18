import os as _os
import sys as _sys

_vendor_dir = _os.path.join(_os.path.dirname(__file__), "vendor")
if _os.path.isdir(_vendor_dir) and _vendor_dir not in _sys.path:
    _sys.path.insert(0, _vendor_dir)

import bpy

from .preferences import FalPreferences
from .app import FalAISceneProperties, FAL_PT_MainPanel, FAL_PT_JobsPanel
from .controllers import FalController
from .job_queue import JobManager


def register() -> None:
    """
    Register the fal.ai addon.
    """
    bpy.utils.register_class(FalPreferences)
    bpy.utils.register_class(FalAISceneProperties)
    bpy.types.Scene.fal = bpy.props.PointerProperty(type=FalAISceneProperties)
    bpy.utils.register_class(FAL_PT_MainPanel)
    FalController.register_all(
        parent_id=FAL_PT_MainPanel.bl_idname,
    )
    bpy.utils.register_class(FAL_PT_JobsPanel)


def unregister() -> None:
    """
    Unregister the fal.ai addon.
    """
    bpy.utils.unregister_class(FalPreferences)
    bpy.utils.unregister_class(FalAISceneProperties)
    if hasattr(bpy.types.Scene, "fal"):
        del bpy.types.Scene.fal
    bpy.utils.unregister_class(FAL_PT_MainPanel)
    FalController.unregister_all()
    bpy.utils.unregister_class(FAL_PT_JobsPanel)
    JobManager.reset()
