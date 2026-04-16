from ...models import ImageUpscalingModel, VideoUpscalingModel
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalUpscaleOperator
from .props import FalUpscalePropertyGroup


class FalUpscaleController(FalController):
    """Controller for image and video upscaling via fal.ai."""

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
            "texture",
        ],
        field_conditions={
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "video_endpoint": lambda ctx, props: props.mode == "VIDEO",
            "image_path": lambda ctx, props: props.source == "FILE",
            "texture": lambda ctx, props: props.source == "TEXTURE",
        },
        field_separators=["mode"],
        endpoint_models={
            "image_endpoint": ImageUpscalingModel,
            "video_endpoint": VideoUpscalingModel,
        },
    )
