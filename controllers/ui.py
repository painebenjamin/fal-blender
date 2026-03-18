import bpy

from dataclasses import dataclass, field

from typing import Any, TypeAlias, ClassVar
from collections.abc import Callable

ConditionFunc: TypeAlias = Callable[[bpy.types.Context, bpy.types.PropertyGroup], bool]

@dataclass
class FalControllerUI:
    field_orders: list[str] = field(default_factory=list)
    field_separators: list[str] = field(default_factory=list)
    field_conditions: dict[str, ConditionFunc] = field(default_factory=dict)

    def status_message(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> str | None:
        """
        Return the status message for the controller.
        """
        return None

    def show_field(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        field_name: str,
    ) -> bool:
        """
        Check if a field should be shown in the UI.
        """
        if not self.field_conditions or field_name not in self.field_conditions:
            return True
        return self.field_conditions[field_name](context, props)

    def draw_field(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        field_name: str,
    ) -> None:
        """
        Draw a field in the UI.
        """
        if self.show_field(context, props, field_name):
            layout.prop(props, field_name)
            if field_name in self.field_separators:
                layout.separator()

    def draw_status(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> None:
        """
        Draw the status message for the controller.
        """
        message = self.status_message(context, props)
        if message:
            layout.label(text=message)

    def draw_operator(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        operator_name: str,
        operator_icon: str,
        operator_size: float = 1.5,
    ) -> None:
        """
        Draw the operator for the controller.
        """
        row = layout.row()
        row.scale_y = operator_size
        row.operator(operator_name, icon=operator_icon)

    def draw(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        operator_name: str,
        operator_icon: str,
        operator_size: float = 1.5,
    ) -> None:
        """
        Draw the UI for the controller.
        """
        visited_fields = set()
        for field_name in self.field_orders:
            if field_name in visited_fields:
                continue
            self.draw_field(layout, context, props, field_name)
            visited_fields.add(field_name)
    
        for field_name in props.keys():
            if field_name in visited_fields:
                continue
            self.draw_field(layout, context, props, field_name)
            visited_fields.add(field_name)

        self.draw_status(layout, context, props)
        self.draw_operator(layout, context, props, operator_name, operator_icon, operator_size)