from __future__ import annotations

import os

import bpy

# For extensions, __package__ is "bl_ext.user_default.fal_ai" (or similar).
# AddonPreferences.bl_idname MUST match this, not a hardcoded string.
_addon_package = __package__


class FalPreferences(bpy.types.AddonPreferences):
    """
    Preferences for the fal.ai addon.
    """

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
        default="",
    )

    auto_import: bpy.props.BoolProperty(
        name="Auto-Import Results",
        description="Automatically import generated assets into the scene",
        default=True,
    )

    def draw(self, context: bpy.types.Context) -> None:
        """
        Draw the preferences.
        """
        layout = self.layout
        layout.prop(self, "api_key")

        env_key = os.environ.get("FAL_KEY", "")
        if not self.api_key and env_key:
            box = layout.box()
            box.label(
                text=f"Using FAL_KEY from environment (…{env_key[-4:]})",
                icon="CHECKMARK",
            )
        elif not self.api_key and not env_key:
            box = layout.box()
            box.label(text="No API key set!", icon="ERROR")
            box.label(text="Set above, or export FAL_KEY in your shell")
            box.operator("wm.url_open", text="Get a key at fal.ai").url = (
                "https://fal.ai/dashboard/keys"
            )

        layout.prop(self, "output_dir")
        layout.prop(self, "auto_import")


def get_api_key() -> str | None:
    """
    Get the fal API key from preferences or environment.

    Returns:
        The API key if found, otherwise None.
    """
    try:
        prefs = bpy.context.preferences.addons[_addon_package].preferences
        key = prefs.api_key
    except (KeyError, AttributeError):
        key = ""
    if not key:
        key = os.environ.get("FAL_KEY", "")
    return key or None


def ensure_api_key() -> str:
    """
    Get the API key or raise an error.

    Returns:
        The API key.

    Raises:
        RuntimeError: If no API key is set.
    """
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
