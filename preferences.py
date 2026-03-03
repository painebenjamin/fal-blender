# SPDX-License-Identifier: Apache-2.0
"""Addon preferences — API key, output dir, defaults."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]
import os

# For extensions, __package__ is "bl_ext.user_default.fal_ai" (or similar).
# AddonPreferences.bl_idname MUST match this, not a hardcoded string.
_addon_package = __package__


class FalPreferences(bpy.types.AddonPreferences):
    bl_idname = _addon_package

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Your fal.ai API key (get one at fal.ai/dashboard/keys)",
        subtype="PASSWORD",
        default="",
    )

    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        description="Where to save generated assets",
        subtype="DIR_PATH",
        default="//fal_output/",
    )

    auto_import: bpy.props.BoolProperty(
        name="Auto-Import Results",
        description="Automatically import generated assets into the scene",
        default=True,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "api_key")
        layout.prop(self, "output_dir")
        layout.prop(self, "auto_import")

        if not self.api_key and not os.environ.get("FAL_KEY"):
            box = layout.box()
            box.label(text="No API key set!", icon="ERROR")
            box.label(text="Get your key at: fal.ai/dashboard/keys")
            box.operator(
                "wm.url_open", text="Open fal.ai Dashboard"
            ).url = "https://fal.ai/dashboard/keys"


def get_api_key() -> str | None:
    """Get the fal API key from preferences or environment."""
    try:
        prefs = bpy.context.preferences.addons[_addon_package].preferences
        key = prefs.api_key
    except (KeyError, AttributeError):
        key = ""
    if not key:
        key = os.environ.get("FAL_KEY", "")
    return key or None


def ensure_api_key() -> str:
    """Get the API key or raise an error."""
    key = get_api_key()
    if not key:
        raise RuntimeError(
            "No fal.ai API key configured. "
            "Set it in Edit > Preferences > Add-ons > fal.ai, "
            "or set the FAL_KEY environment variable."
        )
    # Set in env so fal_client picks it up
    os.environ["FAL_KEY"] = key
    return key


_classes = (FalPreferences,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
