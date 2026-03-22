from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import ClassVar

import bpy

from ..utils import snake_case


class FalOperator(metaclass=ABCMeta):
    """Abstract base class for fal.ai Blender operators."""

    label: ClassVar[str]
    description: ClassVar[str]
    _operator_class: ClassVar[type[bpy.types.Operator]]
    _operator_instance: bpy.types.Operator

    def __init__(self, operator_instance: bpy.types.Operator) -> None:
        """Initialize with a reference to the Blender operator instance."""
        self._operator_instance = operator_instance

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Check if the operator is enabled.
        """
        return True

    @classmethod
    def get_name(cls) -> str:
        """
        Return the name of the operator.
        """
        return f"fal.{snake_case(cls.__name__)}"

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator.
        """
        print(
            "modal() called but not implemented - you should implement this in your subclass if you want to use modal operators"
        )
        return {"PASS_THROUGH"}

    def report(self, levels: set[str], message: str) -> None:
        """
        Report a message to the user.
        """
        self._operator_instance.report(levels, message)

    @abstractmethod
    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Execute the operator logic and return a Blender status set."""
        pass

    @classmethod
    def operator(
        cls,
        props_alias: str,
    ) -> bpy.types.Operator:
        """
        Dynamically create a new operator class that wraps the operator.
        """
        if not hasattr(cls, "_operator_class"):

            class Operator(bpy.types.Operator):
                """Blender operator wrapper generated for a FalOperator subclass."""

                bl_idname = cls.get_name()
                bl_label = getattr(cls, "label", cls.__name__)
                bl_description = str(getattr(cls, "description", cls.__doc__))
                bl_options = {"REGISTER", "UNDO"}

                @classmethod
                def poll(operator_cls, context: bpy.types.Context) -> bool:
                    """Return whether the operator can be executed in the current context."""
                    props = getattr(context.scene, props_alias)
                    return cls.enabled(context, props)

                def _get_operator_instance(self) -> FalOperator:
                    """Return the cached FalOperator instance, creating it if needed."""
                    if not hasattr(self, "_operator_instance"):
                        self._operator_instance = cls(self)
                    return self._operator_instance

                def execute(self, context: bpy.types.Context) -> set[str]:
                    """Execute the operator."""
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance()(context, props)

                def invoke(
                    self, context: bpy.types.Context, event: bpy.types.Event
                ) -> set[str]:
                    """Invoke the operator with the triggering event."""
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance()(
                        context, props, event, invoke=True
                    )

                def modal(
                    self, context: bpy.types.Context, event: bpy.types.Event
                ) -> set[str]:
                    """Handle modal events during long-running operations."""
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance().modal(context, props, event)

            cls._operator_class = Operator
        return cls._operator_class
