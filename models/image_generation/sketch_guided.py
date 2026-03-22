from typing import Any

from ..base import VisualFalModel
from .base import NanoBanana, NanoBanana2, NanoBananaPro

__all__ = [
    "SketchGuidedImageGenerationModel",
    "NanoBananaSketchGuidedImageGenerationModel",
    "NanoBananaProSketchGuidedImageGenerationModel",
    "NanoBanana2SketchGuidedImageGenerationModel",
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
        system_prompt = params.pop("system_prompt", "")
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


# TODO: FLUX.2 Flex Maybe?
