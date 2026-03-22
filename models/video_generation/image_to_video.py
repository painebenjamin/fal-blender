from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel
from .base import (
    LTX2DistilledVideoModel,
    LTX2VideoModel,
    Wan22TurboVideoModel,
    Wan22VideoModel,
)

__all__ = [
    "ImageToVideoModel",
    "Wan22ImageToVideoModel",
    "Wan22TurboImageToVideoModel",
    "LTX2ImageToVideoModel",
    "LTX2DistilledImageToVideoModel",
]


class ImageToVideoModel(VisualFalModel):
    """Base model for image-to-video generation."""

    image_url_parameter: ClassVar[str | None] = "image_url"
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for image-to-video generation."""
        params: dict[str, Any] = dict(cls.static_parameters)
        prompt = kwargs.get("prompt", "")
        if prompt:
            params["prompt"] = prompt
        enable = kwargs.get("enable_prompt_expansion", True)
        params["enable_prompt_expansion"] = enable
        params["expand_prompt"] = enable

        image_url = kwargs.get("image_url")
        if image_url:
            params["image_url"] = image_url

        duration = kwargs.get("duration")
        if duration:
            params["duration"] = duration
        return params


class Wan22ImageToVideoModel(ImageToVideoModel, Wan22VideoModel):
    """Wan 2.2 image-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/image-to-video"


class Wan22TurboImageToVideoModel(ImageToVideoModel, Wan22TurboVideoModel):
    """Wan 2.2 turbo image-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/image-to-video/turbo"


class LTX2ImageToVideoModel(ImageToVideoModel, LTX2VideoModel):
    """LTX-2 19B image-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/image-to-video"


class LTX2DistilledImageToVideoModel(ImageToVideoModel, LTX2DistilledVideoModel):
    """LTX-2 19B distilled image-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/distilled/image-to-video"
