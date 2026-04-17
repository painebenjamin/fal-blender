from typing import Any

from ..base import VisualFalModel
from .base import NanoBanana, NanoBanana2, NanoBananaPro

__all__ = [
    "SketchGuidedImageGenerationModel",
    "NanoBananaSketchGuidedImageGenerationModel",
    "NanoBananaProSketchGuidedImageGenerationModel",
    "NanoBanana2SketchGuidedImageGenerationModel",
    "GPTImage15EditModel",
    "Seedream45EditModel",
    "Seedream5LiteEditModel",
]


class SketchGuidedImageGenerationModel(VisualFalModel):
    """Base class for sketch-guided image generation models that transform sketches into images."""

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        prompt = params.pop("prompt", "")
        # system_prompt comes from kwargs, not params (parent doesn't pass it through)
        system_prompt = kwargs.get("system_prompt", "")
        if system_prompt and prompt:
            prompt = f"{system_prompt}\n\nFollow the user's prompt: {prompt}"
        elif system_prompt and not prompt:
            prompt = system_prompt
        params["prompt"] = prompt
        return params


class NanoBananaSketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBanana
):
    """Sketch-guided image generation using the Nano Banana model."""

    endpoint = "fal-ai/nano-banana/edit"
    image_urls_parameter = "image_urls"


class NanoBananaProSketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBananaPro
):
    """Sketch-guided image generation using the Nano Banana Pro model."""

    endpoint = "fal-ai/nano-banana-pro/edit"
    image_urls_parameter = "image_urls"


class NanoBanana2SketchGuidedImageGenerationModel(
    SketchGuidedImageGenerationModel, NanoBanana2
):
    """Sketch-guided image generation using the Nano Banana 2 model."""

    endpoint = "fal-ai/nano-banana-2/edit"
    image_urls_parameter = "image_urls"


class GPTImage15EditModel(SketchGuidedImageGenerationModel):
    """GPT Image 1.5 edit model.

    The API accepts only three fixed ``image_size`` values — 1024x1024 (1:1),
    1536x1024 (3:2), 1024x1536 (2:3). Requests are mapped by closest aspect
    ratio so a 1920x1080 request lands on ``1536x1024`` instead of falling
    through as raw width/height the endpoint would reject.
    """

    display_name = "GPT Image 1.5 Edit"
    endpoint = "fal-ai/gpt-image-1.5/edit"
    image_urls_parameter = "image_urls"

    _SIZE_CHOICES: list[tuple[str, int, int]] = [
        ("1024x1024", 1024, 1024),
        ("1536x1024", 1536, 1024),
        ("1024x1536", 1024, 1536),
    ]

    @classmethod
    def _choose_image_size(cls, width: int, height: int) -> str:
        target = width / height if height else 1.0
        label, _, _ = min(
            cls._SIZE_CHOICES,
            key=lambda item: abs(target - item[1] / item[2]),
        )
        return label

    @classmethod
    def _get_size_parameters(cls, width: int, height: int) -> dict[str, Any]:
        return {"image_size": cls._choose_image_size(width, height)}

    @classmethod
    def describe_output_size(cls, width: int, height: int) -> str:
        return cls._choose_image_size(width, height)


class Seedream45EditModel(SketchGuidedImageGenerationModel):
    """Seedream 4.5 edit model."""

    display_name = "Seedream 4.5 Edit"
    endpoint = "fal-ai/bytedance/seedream/v4.5/edit"
    image_urls_parameter = "image_urls"


class Seedream5LiteEditModel(SketchGuidedImageGenerationModel):
    """Seedream 5 Lite edit model."""

    display_name = "Seedream 5 Lite Edit"
    endpoint = "fal-ai/bytedance/seedream/v5/lite/edit"
    image_urls_parameter = "image_urls"
