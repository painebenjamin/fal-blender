from ..base import VisualFalModel

__all__ = [
    "ImageUpscalingModel",
    "SeedVR29BImageUpscalingModel",
]


class ImageUpscalingModel(VisualFalModel):
    pass


class SeedVR29BImageUpscalingModel(ImageUpscalingModel):
    endpoint = "fal-ai/seedvr/upscale/image"
    display_name = "SeedVR2 9B"
    image_url_parameter = "image_url"
