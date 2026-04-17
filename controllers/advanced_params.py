"""Advanced parameters UI for power users.

Provides a UIList-based interface for arbitrary key-value parameters
that get merged into API requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "FalAdvancedParameter",
    "FAL_UL_AdvancedParamsList",
    "FAL_OT_AddAdvancedParam",
    "FAL_OT_RemoveAdvancedParam",
    "register_advanced_params",
    "unregister_advanced_params",
    "draw_advanced_params",
    "get_advanced_params_dict",
]


class FalAdvancedParameter(bpy.types.PropertyGroup):
    """A single key-value parameter for API requests."""

    key: bpy.props.StringProperty(
        name="Key",
        description="Parameter name (e.g. 'guidance_scale')",
        default="",
    )
    value: bpy.props.StringProperty(
        name="Value",
        description="Parameter value (strings, numbers, booleans supported)",
        default="",
    )
    value_type: bpy.props.EnumProperty(
        name="Type",
        description="Value type for proper JSON encoding",
        items=[
            ("STRING", "String", "Text value"),
            ("INT", "Integer", "Whole number"),
            ("FLOAT", "Float", "Decimal number"),
            ("BOOL", "Boolean", "True/False"),
        ],
        default="STRING",
    )


class FAL_UL_AdvancedParamsList(bpy.types.UIList):
    """UIList for displaying advanced parameters."""

    bl_idname = "FAL_UL_AdvancedParamsList"

    def draw_item(
        self,
        context: bpy.types.Context,
        layout: bpy.types.UILayout,
        data: bpy.types.AnyType,
        item: FalAdvancedParameter,
        icon: int,
        active_data: bpy.types.AnyType,
        active_property: str,
        index: int = 0,
        flt_flag: int = 0,
    ) -> None:
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(item, "key", text="", emboss=False)
            row.prop(item, "value_type", text="", emboss=True)
            row.prop(item, "value", text="", emboss=False)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.key or "(empty)")


def _make_add_operator(props_path: str) -> type[bpy.types.Operator]:
    """Create an operator class for adding advanced parameters."""

    class FAL_OT_AddAdvancedParam(bpy.types.Operator):
        """Add a new advanced parameter."""

        bl_idname = f"fal.add_advanced_param_{props_path.replace('.', '_')}"
        bl_label = "Add Parameter"
        bl_description = "Add a new advanced parameter"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: bpy.types.Context) -> set[str]:
            props = eval(f"context.scene.{props_path}")
            item = props.advanced_params.add()
            item.key = ""
            item.value = ""
            props.advanced_params_index = len(props.advanced_params) - 1
            return {"FINISHED"}

    return FAL_OT_AddAdvancedParam


def _make_remove_operator(props_path: str) -> type[bpy.types.Operator]:
    """Create an operator class for removing advanced parameters."""

    class FAL_OT_RemoveAdvancedParam(bpy.types.Operator):
        """Remove the selected advanced parameter."""

        bl_idname = f"fal.remove_advanced_param_{props_path.replace('.', '_')}"
        bl_label = "Remove Parameter"
        bl_description = "Remove the selected advanced parameter"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: bpy.types.Context) -> set[str]:
            props = eval(f"context.scene.{props_path}")
            idx = props.advanced_params_index
            if 0 <= idx < len(props.advanced_params):
                props.advanced_params.remove(idx)
                props.advanced_params_index = max(0, idx - 1)
            return {"FINISHED"}

    return FAL_OT_RemoveAdvancedParam


# Storage for dynamically created operators
_registered_operators: dict[str, tuple[type, type]] = {}


def register_advanced_params(props_path: str) -> tuple[str, str]:
    """Register add/remove operators for a specific props path.

    Args:
        props_path: Dot-separated path to props (e.g. 'falrendercontroller_props')

    Returns:
        Tuple of (add_op_idname, remove_op_idname)
    """
    if props_path in _registered_operators:
        add_cls, remove_cls = _registered_operators[props_path]
        return add_cls.bl_idname, remove_cls.bl_idname

    add_cls = _make_add_operator(props_path)
    remove_cls = _make_remove_operator(props_path)

    bpy.utils.register_class(add_cls)
    bpy.utils.register_class(remove_cls)

    _registered_operators[props_path] = (add_cls, remove_cls)
    return add_cls.bl_idname, remove_cls.bl_idname


def unregister_advanced_params(props_path: str) -> None:
    """Unregister operators for a specific props path."""
    if props_path not in _registered_operators:
        return

    add_cls, remove_cls = _registered_operators.pop(props_path)
    bpy.utils.unregister_class(remove_cls)
    bpy.utils.unregister_class(add_cls)


def draw_advanced_params(
    layout: bpy.types.UILayout,
    props: bpy.types.PropertyGroup,
    props_path: str,
    collapsed: bool = True,
) -> None:
    """Draw the advanced parameters UI section.

    Args:
        layout: Parent layout to draw into
        props: PropertyGroup containing advanced_params CollectionProperty
        props_path: Path for operator registration
        collapsed: Whether to start collapsed (default True)
    """
    # Ensure operators are registered
    add_op, remove_op = register_advanced_params(props_path)

    # Collapsible header
    box = layout.box()
    row = box.row()
    row.prop(
        props,
        "show_advanced_params",
        icon="TRIA_DOWN" if props.show_advanced_params else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    row.label(text="Advanced Parameters")

    if not props.show_advanced_params:
        return

    # UIList
    row = box.row()
    row.template_list(
        FAL_UL_AdvancedParamsList.bl_idname,
        "",
        props,
        "advanced_params",
        props,
        "advanced_params_index",
        rows=3,
    )

    # Add/Remove buttons
    col = row.column(align=True)
    col.operator(add_op, icon="ADD", text="")
    col.operator(remove_op, icon="REMOVE", text="")


def get_advanced_params_dict(props: bpy.types.PropertyGroup) -> dict:
    """Convert advanced params collection to a dict for API requests.

    Handles type conversion based on value_type.
    """
    result = {}
    if not hasattr(props, "advanced_params"):
        return result

    for param in props.advanced_params:
        key = param.key.strip()
        if not key:
            continue

        value = param.value
        try:
            if param.value_type == "INT":
                result[key] = int(value)
            elif param.value_type == "FLOAT":
                result[key] = float(value)
            elif param.value_type == "BOOL":
                result[key] = value.lower() in ("true", "1", "yes", "on")
            else:  # STRING
                result[key] = value
        except (ValueError, AttributeError):
            # Fall back to string on conversion errors
            result[key] = value

    return result


def register() -> None:
    """Register base classes."""
    bpy.utils.register_class(FalAdvancedParameter)
    bpy.utils.register_class(FAL_UL_AdvancedParamsList)


def unregister() -> None:
    """Unregister base classes and all dynamic operators."""
    # Unregister all dynamic operators
    for props_path in list(_registered_operators.keys()):
        unregister_advanced_params(props_path)

    bpy.utils.unregister_class(FAL_UL_AdvancedParamsList)
    bpy.utils.unregister_class(FalAdvancedParameter)
