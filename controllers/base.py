from abc import ABCMeta, abstractmethod
from typing import ClassVar

import bpy

from .operators import FalOperator
from .ui import FalControllerUI

class FalController(metaclass=ABCMeta):
    enabled: ClassVar[bool] = True
    display_name: ClassVar[str | None] = None
    description: ClassVar[str | None] = None
    icon: ClassVar[str] = "FILE_IMAGE"
    operator_class: ClassVar[type[FalOperator]]
    properties_class: ClassVar[type[bpy.types.PropertyGroup]]
    ui: ClassVar[FalControllerUI] = FalControllerUI()

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if the controller is available.
        """
        return getattr(cls, "properties_class", None) is not None and \
            getattr(cls, "operator_class", None) is not None and \
            getattr(cls, "panel_class", None) is not None and \
            cls.enabled

    @classmethod
    def get_display_name(cls) -> str:
        """
        Return the display name for the controller.
        """
        return cls.display_name or cls.__name__

    @classmethod
    def get_description(cls) -> str:
        """
        Return the description for the controller.
        """
        return cls.description or ""

    @classmethod
    def get_props_alias(cls) -> str:
        """
        Return the alias for the properties class.
        """
        return f"{cls.__name__.lower()}_props"

    @classmethod
    def operator(cls) -> type[bpy.types.Operator]:
        """
        Return the operator class for the controller.
        """
        if getattr(cls, "operator_class", None) is None:
            raise NotImplementedError("operator_class must be set")
        return cls.operator_class.operator(
            props_alias=cls.get_props_alias(),
        )

    @classmethod
    def panel(
        cls,
        parent_id: str,
        show_condition: ConditionFunc | None = None,
    ) -> type[bpy.types.Panel]:
        """
        Return the panel class for the controller.
        """
        if not hasattr(cls, "_panel_class"):
            operator_class = cls.operator()

            class Panel(bpy.types.Panel):
                bl_idname = f"fal.{cls.__name__}"
                bl_label = getattr(operator_class, "label", operator_class.__name__)
                bl_description = getattr(operator_class, "description", operator_class.__doc__)
                bl_space_type = "VIEW_3D"
                bl_region_type = "UI"
                bl_category = "fal.ai"
                bl_parent_id = parent_id

            @classmethod
            def poll(cls, context: bpy.types.Context) -> bool:
                if show_condition is None:
                    return True
                props = getattr(context.scene, cls.get_props_alias())
                return show_condition(context, props)

            @classmethod
            def draw(self, context: bpy.types.Context) -> None:
                layout = self.layout
                props = getattr(context.scene, cls.get_props_alias())
                cls.ui.draw(
                    layout, context, props,
                    operator_name=operator_class.get_name(),
                    operator_icon=cls.icon,
                )

            cls._panel_class = Panel
        return cls._panel_class

    @classmethod
    def register_properties(cls) -> None:
        """
        Register the properties class for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        bpy.utils.register_class(cls.properties_class)

    @classmethod
    def unregister_properties(cls) -> None:
        """
        Unregister the properties class for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        bpy.utils.unregister_class(cls.properties_class)

    @classmethod
    def register_operator(cls) -> None:
        """
        Register the operator class for the controller.
        """
        if getattr(cls, "operator_class", None) is None:
            raise NotImplementedError("operator_class must be set")
        bpy.utils.register_class(cls.operator())
    
    @classmethod
    def unregister_operator(cls) -> None:
        """
        Unregister the operator class for the controller.
        """
        if getattr(cls, "operator_class", None) is None:
            raise NotImplementedError("operator_class must be set")
        bpy.utils.unregister_class(cls.operator())

    @classmethod
    def register_panel(cls) -> None:
        """
        Register the panel class for the controller.
        """
        if getattr(cls, "panel_class", None) is None:
            raise NotImplementedError("panel_class must be set")
        bpy.utils.register_class(cls.panel())

    @classmethod
    def unregister_panel(cls) -> None:
        """
        Unregister the panel class for the controller.
        """
        if getattr(cls, "panel_class", None) is None:
            raise NotImplementedError("panel_class must be set")
        bpy.utils.unregister_class(cls.panel())

    @classmethod
    def register_properties_pointer(cls) -> None:
        """
        Register the properties pointer for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        setattr(
            bpy.types.Scene,
            cls.get_props_alias(),
            bpy.props.PointerProperty(type=cls.properties_class)
        )

    @classmethod
    def unregister_properties_pointer(cls) -> None:
        """
        Unregister the properties pointer for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        delattr(bpy.types.Scene, cls.get_props_alias())

    @classmethod
    def register(cls) -> None:
        """
        Register the controller.
        """
        if not cls.is_available():
            return
        cls.register_properties()
        cls.register_operator()
        cls.register_panel()
        cls.register_properties_pointer()

    @classmethod
    def unregister(cls) -> None:
        """
        Unregister the controller.
        """
        if not cls.is_available():
            return
        cls.unregister_properties()
        cls.unregister_operator()
        cls.unregister_panel()
        cls.unregister_properties_pointer()

    @classmethod
    def register_all(cls) -> None:
        """
        Register all controllers.
        """
        for subcls in cls.__subclasses__():
            if subcls.is_available():
                subcls.register()

    @classmethod
    def unregister_all(cls) -> None:
        """
        Unregister all controllers.
        """
        for subcls in cls.__subclasses__():
            if subcls.is_available():
                subcls.unregister()

    @classmethod
    def enumerate(cls) -> list[tuple[str, str, str]]:
        """
        Returns a list of all available controllers.
        """
        return [
            (subcls.__name__, subcls.get_display_name(), subcls.get_description(), subcls.icon)
            for subcls in cls.__subclasses__()
            if subcls.is_available()
        ]