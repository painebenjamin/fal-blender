from ..base import VisualFalModel
from .base import NanoBanana, NanoBananaPro, NanoBanana2

from typing import Any

__all__ = [
    "SketchGuidedImageGenerationModel",
    "NanoBananaSketchGuidedImageGenerationModel",
    "NanoBananaProSketchGuidedImageGenerationModel",
    "NanoBanana2SketchGuidedImageGenerationModel",
]

class SketchGuidedImageGenerationModel(VisualFalModel):
    @classmethod
    def parameters(
        cls,
        **kwargs: Any
    ) -> dict[str, Any]:
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

class NanoBananaSketchGuidedImageGenerationModel(SketchGuidedImageGenerationModel, NanoBanana):
    endpoint = "fal-ai/nano-banana/edit"
    image_urls_parameter = "image_urls"

class NanoBananaProSketchGuidedImageGenerationModel(SketchGuidedImageGenerationModel, NanoBananaPro):
    endpoint = "fal-ai/nano-banana-pro/edit"
    image_urls_parameter = "image_urls"

class NanoBanana2SketchGuidedImageGenerationModel(SketchGuidedImageGenerationModel, NanoBanana2):
    endpoint = "fal-ai/nano-banana-2/edit"
    image_urls_parameter = "image_urls"

# TODO: FLUX.2 Flex Maybe?