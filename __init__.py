# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Features and Labels, Inc.
"""fal.ai Blender Extension — AI-powered generation suite."""

from . import preferences, endpoints  # noqa: F401
from .core import job_queue  # noqa: F401
from .ui import panels  # noqa: F401
from .operators import (  # noqa: F401
    texture,
    generate_3d,
    upscale,
    neural_render,
    video,
    audio,
    mesh_ops,
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
    video,
    audio,
    mesh_ops,
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
