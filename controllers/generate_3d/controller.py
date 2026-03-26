from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalGenerate3DOperator
from .props import FalGenerate3DPropertyGroup


class FalGenerate3DController(FalController):
    """Controller for text-to-3D and image-to-3D model generation via fal.ai."""

    display_name = "3D Generation"
    description = "Generate 3D models from text or images using fal.ai"
    icon = "MESH_MONKEY"
    operator_class = FalGenerate3DOperator
    properties_class = FalGenerate3DPropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "mode",
            "text_endpoint",
            "image_endpoint",
            "prompt",
            "enable_prompt_expansion",
            "image_source",
            "image_path",
            "generate_materials",
        ],
        field_conditions={
            "text_endpoint": lambda ctx, props: props.mode == "TEXT",
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "prompt": lambda ctx, props: props.mode == "TEXT",
            "enable_prompt_expansion": lambda ctx, props: props.mode == "TEXT",
            "image_source": lambda ctx, props: props.mode == "IMAGE",
            "image_path": lambda ctx, props: props.mode == "IMAGE"
            and props.image_source == "FILE",
        },
    )
