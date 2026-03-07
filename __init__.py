# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Features and Labels, Inc.
"""fal.ai Blender Extension — AI-powered generation suite."""

# Add vendored dependencies to sys.path (e.g. Pillow installed via pip --target vendor/)
import os as _os
import sys as _sys

_vendor_dir = _os.path.join(_os.path.dirname(__file__), "vendor")
if _os.path.isdir(_vendor_dir) and _vendor_dir not in _sys.path:
    _sys.path.insert(0, _vendor_dir)

from . import preferences, endpoints  # noqa: F401
from .core import job_queue  # noqa: F401
from .ui import panels  # noqa: F401
from .operators import (  # noqa: F401
    texture,
    generate_3d,
    upscale,
    neural_render,
    realtime_refine,
    video,
    audio,
    mesh_ops,
    material,
)

# Registration order matters!
# 1. Preferences (API key)
# 2. Endpoints (no bpy registration needed)
# 3. Job queue core
# 4. ALL operator modules (they register PropertyGroups on Scene)
# 5. Panels LAST (they reference those PropertyGroups)
_modules = [
    preferences,
    endpoints,
    job_queue,
    texture,
    generate_3d,
    upscale,
    neural_render,
    realtime_refine,
    video,
    audio,
    mesh_ops,
    material,
    panels,  # MUST be last — panels reference operator PropertyGroups
]


def register():
    for mod in _modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister():
    for mod in reversed(_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
