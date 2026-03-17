from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any

import bpy

class FalOperator(metaclass=ABCMeta):
    label: ClassVar[str]
    description: ClassVar[str]
    _operator_class: ClassVar[type[bpy.types.Operator]]
    _operator_instance: bpy.types.Operator

    def __init__(self, operator_instance: bpy.types.Operator) -> None:
        self._operator_instance = operator_instance

    @classmethod
    def enabled(cls, context: bpy.types.Context, props: bpy.types.PropertyGroup) -> bool:
        """
        Check if the operator is enabled.
        """
        return True

    @classmethod
    def get_name(cls) -> str:
        """
        Return the name of the operator.
        """
        return f"fal.{cls.__name__}"

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator.
        """
        print("modal() called but not implemented - you should implement this in your subclass if you want to use modal operators")
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
                bl_idname = cls.get_name()
                bl_label = getattr(cls, "label", cls.__name__)
                bl_description = getattr(cls, "description", cls.__doc__)
                bl_options = {"REGISTER", "UNDO"}

                @classmethod
                def poll(cls, context: bpy.types.Context) -> bool:
                    return cls.enabled(context)

                def _get_operator_instance(self) -> FalOperator:
                    if not hasattr(self, "_operator_instance"):
                        self._operator_instance = cls(self)
                    return self._operator_instance

                def execute(self, context: bpy.types.Context) -> set[str]:
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance()(context, props)

                def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance()(context, props, event, invoke=True)

                def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance().modal(context, event, props)
                
            cls._operator_class = Operator
        return cls._operator_class