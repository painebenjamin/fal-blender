from abc import ABCMeta, abstractmethod
from typing import ClassVar

import bpy

from ..utils import snake_case
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
    ) -> type[bpy.types.Panel]:
        """
        Return the panel class for the controller.
        """
        if not hasattr(cls, "_panel_class"):
            operator_class = cls.operator()

            class Panel(bpy.types.Panel):
                bl_idname = f"FAL_PT_{snake_case(cls.__name__)}"
                bl_label = getattr(operator_class, "label", operator_class.__name__)
                bl_description = str(getattr(operator_class, "description", operator_class.__doc__))
                bl_space_type = "VIEW_3D"
                bl_region_type = "UI"
                bl_category = "fal.ai"
                bl_parent_id = parent_id

                @classmethod
                def poll(panel_cls, context: bpy.types.Context) -> bool:
                    return cls.is_available() and context.scene.fal.active_controller == cls.__name__

                def draw(self, context: bpy.types.Context) -> None:
                    layout = self.layout
                    props = getattr(context.scene, cls.get_props_alias())
                    cls.ui.draw(
                        layout, context, props,
                        operator_name=cls.operator_class.get_name(),
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
        if hasattr(cls, "_operator_class"):
            bpy.utils.unregister_class(cls._operator_class)

    @classmethod
    def register_panel(cls, parent_id: str) -> None:
        """
        Register the panel class for the controller.
        """
        bpy.utils.register_class(cls.panel(parent_id=parent_id))

    @classmethod
    def unregister_panel(cls) -> None:
        """
        Unregister the panel class for the controller.
        """
        if hasattr(cls, "_panel_class"):
            bpy.utils.unregister_class(cls._panel_class)

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
    def register(cls, parent_id: str) -> None:
        """
        Register the controller.
        """
        if not cls.is_available():
            return
        cls.register_properties()
        cls.register_operator()
        cls.register_panel(parent_id=parent_id)
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
    def register_all(cls, parent_id: str) -> None:
        """
        Register all controllers.
        """
        for subcls in cls.__subclasses__():
            if subcls.is_available():
                subcls.register(parent_id=parent_id)

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
        unique_id = 0
        def _get_unique_id() -> int:
            nonlocal unique_id
            unique_id += 1
            return unique_id

        return [
            (subcls.__name__, subcls.get_display_name(), subcls.get_description(), subcls.icon, _get_unique_id())
            for subcls in cls.__subclasses__()
            if subcls.is_available()
        ]