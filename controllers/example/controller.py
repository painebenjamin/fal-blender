from __future__ import annotations

import bpy

from ..ui import FalControllerUI
from ..base import FalController
from .operator import FalExampleOperator
from .props import FalExamplePropertyGroup

class FalExampleController(FalController):
    """
    Example controller.
    """
    enabled = False  # Set to True to enable the controller
    display_name = "Example"
    description = "This is an example controller"
    icon = "FILE_IMAGE"
    operator_class = FalExampleOperator
    properties_class = FalExamplePropertyGroup
    # Optional: UI configuration
    ui = FalControllerUI(
        # Order of fields in the UI
        field_orders=[
            "example_property",
        ],
        # Separators between fields in the UI
        field_separators=[
            "example_property",
        ],
        # Conditions for showing fields in the UI
        field_conditions={
            "example_property": lambda context, props: True,
        },
    )