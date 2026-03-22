from ..base import VisualFalModel

__all__ = [
    "VideoUpscalingModel",
    "SeedVR29BVideoUpscalingModel",
]


class VideoUpscalingModel(VisualFalModel):
    """Base model for video upscaling."""

    pass


class SeedVR29BVideoUpscalingModel(VideoUpscalingModel):
    """SeedVR2 9B video upscaling model."""

    endpoint = "fal-ai/seedvr/upscale/video"
    display_name = "SeedVR2 9B"
    video_url_parameter = "video_url"
