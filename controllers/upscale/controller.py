from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalUpscaleOperator
from .props import FalUpscalePropertyGroup


class FalUpscaleController(FalController):
    display_name = "Upscale"
    description = "Upscale images and videos using fal.ai"
    icon = "FULLSCREEN_ENTER"
    operator_class = FalUpscaleOperator
    properties_class = FalUpscalePropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "mode",
            "image_endpoint",
            "video_endpoint",
            "source",
            "image_path",
            "texture_name",
        ],
        field_conditions={
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "video_endpoint": lambda ctx, props: props.mode == "VIDEO",
            "image_path": lambda ctx, props: props.source == "FILE",
            "texture_name": lambda ctx, props: props.source == "TEXTURE",
        },
        field_separators=["mode"],
    )
