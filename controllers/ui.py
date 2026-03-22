from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeAlias

import bpy

ConditionFunc: TypeAlias = Callable[[bpy.types.Context, bpy.types.PropertyGroup], bool]


@dataclass
class FalControllerPanel:
    """Declarative UI layout definition for a fal.ai controller panel."""

    field_orders: list[str] = field(default_factory=list)
    field_separators: list[str] = field(default_factory=list)
    field_conditions: dict[str, ConditionFunc] = field(default_factory=dict)
    field_groupings: list[set[str]] = field(default_factory=list)

    _current_group_seen: set[str] = field(default_factory=set)
    _current_group: set[str] | None = None
    _current_row: bpy.types.UILayout | None = None

    def __post_init__(self) -> None:
        """
        Post-init hook, validate field groupings.

        Fields can only be in one grouping.
        """
        seen_fields = set()
        for group in self.field_groupings:
            for field in group:
                if field in seen_fields:
                    raise ValueError(f"Field {field} is in multiple groupings")
                seen_fields.add(field)

    def _get_group_for_field(self, field_name: str) -> set[str] | None:
        """
        Get the group for a field.
        """
        for group in self.field_groupings:
            if field_name in group:
                return group
        return None

    def _flush_current_group(self) -> None:
        """
        Flush the current group.
        """
        self._current_group = None
        self._current_row = None
        self._current_group_seen.clear()

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
            group = self._get_group_for_field(field_name)
            if group:
                if self._current_group != group:
                    self._current_group = group
                    self._current_row = layout.row()
                    self._current_group_seen.clear()

                self._current_row.prop(props, field_name)
                self._current_group_seen.add(field_name)

                if len(self._current_group_seen) == len(group):
                    self._flush_current_group()
                    if any(field_name in self.field_separators for field_name in group):
                        layout.separator()
            else:
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
        self.draw_operator(
            layout, context, props, operator_name, operator_icon, operator_size
        )
        self._flush_current_group()
