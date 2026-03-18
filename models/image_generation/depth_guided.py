from typing import Any

from ..base import VisualFalModel
from .base import FLUX1Dev, ZImageTurbo

__all__ = [
    "DepthGuidedImageGenerationModel",
    "ZImageTurboDepthGuidedImageGenerationModel",
    "FLUX1DevDepthGuidedImageGenerationModel",
]


class DepthGuidedImageGenerationModel(VisualFalModel):
    pass


class ZImageTurboDepthGuidedImageGenerationModel(
    DepthGuidedImageGenerationModel, ZImageTurbo
):
    endpoint = "fal-ai/z-image/turbo/controlnet"
    image_url_parameter = "image_url"
    prompt_expansion_parameter = "enable_prompt_expansion"


class FLUX1DevDepthGuidedImageGenerationModel(
    DepthGuidedImageGenerationModel, FLUX1Dev
):
    endpoint = "fal-ai/flux-general"
    image_url_parameter = "image_url"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["controlnet_unions"] = [
            {
                "path": "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro",
                "controls": [
                    {
                        "control_image_url": params.pop("image_url", None),
                        "control_mode": "depth",
                    }
                ],
            },
        ]
        return params
