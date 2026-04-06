from ...models import DepthVideoModel, ImageToVideoModel, TextToVideoModel
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalDepthVideoOperator, FalVideoOperator
from .props import FalDepthVideoPropertyGroup, FalVideoPropertyGroup


class FalVideoController(FalController):
    """Text-to-video and image-to-video (VSE panel only)."""

    display_name = "Video"
    description = "Generate video from text or image using fal.ai"
    icon = "SEQUENCE"
    operator_class = FalVideoOperator
    properties_class = FalVideoPropertyGroup
    panel_vse = FalControllerPanel(
        field_orders=[
            "mode",
            "text_endpoint",
            "image_endpoint",
            "prompt",
            "enable_prompt_expansion",
            "image_source",
            "image_path",
            "use_scene_duration",
            "duration",
        ],
        field_conditions={
            "text_endpoint": lambda ctx, props: props.mode == "TEXT",
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "image_source": lambda ctx, props: props.mode == "IMAGE",
            "image_path": lambda ctx, props: props.mode == "IMAGE"
            and props.image_source == "FILE",
            "duration": lambda ctx, props: not props.use_scene_duration,
        },
        endpoint_models={
            "text_endpoint": TextToVideoModel,
            "image_endpoint": ImageToVideoModel,
        },
    )


class FalDepthVideoController(FalController):
    """Depth-conditioned video generation (3D panel only)."""

    display_name = "Depth Video"
    description = "Render depth animation and generate video via fal.ai"
    icon = "VIEW_CAMERA"
    operator_class = FalDepthVideoOperator
    properties_class = FalDepthVideoPropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "depth_endpoint",
            "prompt",
            "enable_prompt_expansion",
            "use_scene_duration",
            "duration",
            "use_scene_resolution",
            "depth_use_first_frame",
            "depth_image_source",
            "depth_image_path",
            "depth_texture_name",
        ],
        field_conditions={
            "duration": lambda ctx, props: not props.use_scene_duration,
            "depth_image_source": lambda ctx, props: props.depth_use_first_frame,
            "depth_image_path": lambda ctx, props: props.depth_use_first_frame
            and props.depth_image_source == "FILE",
            "depth_texture_name": lambda ctx, props: props.depth_use_first_frame
            and props.depth_image_source == "TEXTURE",
        },
        endpoint_models={
            "depth_endpoint": DepthVideoModel,
        },
    )
