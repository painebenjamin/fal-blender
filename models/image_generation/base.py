from ..base import VisualFalModel

__all__ = [
    "NanoBanana",
    "NanoBananaPro",
    "NanoBanana2",
    "ZImageBase",
    "ZImageTurbo",
    "FLUX1Dev",
    "FLUX2Klein9B",
]


class NanoBanana(VisualFalModel):
    """Nano Banana image generation model with 1K resolution support."""

    display_name = "Nano Banana"
    use_resolution_aspect_ratio = True
    aspect_ratios = [
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
    ]
    resolutions = {"1K": 1024}  # Only 1K resolution is supported for NB1


class NanoBananaPro(VisualFalModel):
    """Nano Banana Pro image generation model with 1K/2K/4K resolution support."""

    display_name = "Nano Banana Pro"
    use_resolution_aspect_ratio = True
    aspect_ratios = [
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
    ]
    resolutions = {
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }


class NanoBanana2(VisualFalModel):
    """Nano Banana 2 image generation model with extended aspect ratios and 0.5K-4K resolution support."""

    display_name = "Nano Banana 2"
    use_resolution_aspect_ratio = True
    aspect_ratios = [
        "8:1",
        "4:1",
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
        "1:4",
        "1:8",
    ]
    resolutions = {
        "0.5K": 512,
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }


class ZImageTurbo(VisualFalModel):
    """Z-Image Turbo image generation model optimized for speed."""

    display_name = "Z-Image Turbo"
    size_parameter = "image_size"


class ZImageBase(VisualFalModel):
    """Z-Image Base image generation model."""

    display_name = "Z-Image Base"
    size_parameter = "image_size"


class FLUX1Dev(VisualFalModel):
    """FLUX.1 [dev] image generation model."""

    display_name = "FLUX.1 [dev]"
    size_parameter = "image_size"


class FLUX2Klein9B(VisualFalModel):
    """FLUX.2 Klein 9B image generation model."""

    display_name = "FLUX.2 Klein 9B"
    size_parameter = "image_size"
