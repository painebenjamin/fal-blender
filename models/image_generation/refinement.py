from ..base import VisualFalModel
from .base import NanoBanana, NanoBananaPro, NanoBanana2, ZImageTurbo, FLUX1Dev, FLUX2Klein9B

from typing import Any

__all__ = [
    "ImageRefinementModel",
    "NanoBananaImageRefinementModel",
    "NanoBananaProImageRefinementModel",
    "NanoBanana2ImageRefinementModel",
    "ZImageTurboImageRefinementModel",
    "FLUX1DevImageRefinementModel",
    "FLUX2Klein9BImageRefinementModel",
]

class ImageRefinementModel(VisualFalModel):
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
        if system_prompt and prompt and not prompt.startswith(system_prompt):
            prompt = f"{system_prompt}\n\nFollow the user's prompt: {prompt}"
        elif system_prompt and not prompt:
            prompt = system_prompt
        params["prompt"] = prompt
        return params

class ImageToImageRefinementModel(ImageRefinementModel):
    @classmethod
    def parameters(
        cls,
        **kwargs: Any
    ) -> dict[str, Any]:
        params = super().parameters(**kwargs)
        params["strength"] = kwargs.get("strength", 0.5)
        return params

class NanoBananaImageRefinementModel(ImageRefinementModel, NanoBanana):
    endpoint = "fal-ai/nano-banana/edit"
    image_urls_parameter = "image_urls"

class NanoBananaProImageRefinementModel(ImageRefinementModel, NanoBananaPro):
    endpoint = "fal-ai/nano-banana-pro/edit"
    image_urls_parameter = "image_urls"

class NanoBanana2ImageRefinementModel(ImageRefinementModel, NanoBanana2):
    endpoint = "fal-ai/nano-banana-2/edit"
    image_urls_parameter = "image_urls"

class ZImageTurboImageRefinementModel(ImageRefinementModel, ZImageTurbo):
    endpoint = "fal-ai/z-image/turbo/image-to-image"
    image_url_parameter = "image_url"
    prompt_expansion_parameter = "enable_prompt_expansion"

class FLUX1DevImageRefinementModel(ImageToImageRefinementModel, FLUX1Dev):
    endpoint = "fal-ai/flux/dev/image-to-image"
    image_url_parameter = "image_url"

class FLUX2Klein9BImageRefinementModel(ImageToImageRefinementModel, FLUX2Klein9B):
    endpoint = "fal-ai/flux-2/klein/9b/edit"
    image_urls_parameter = "image_urls"
