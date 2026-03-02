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
)

_modules = [
    preferences,
    endpoints,
    job_queue,
    panels,
    texture,
    generate_3d,
    upscale,
    neural_render,
]


def register():
    for mod in _modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister():
    for mod in reversed(_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
