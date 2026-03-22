from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel

__all__ = [
    "ImageToVideoModel",
    "Kling3ProImageToVideoModel",
    "Wan21ImageToVideoModel",
]


class ImageToVideoModel(VisualFalModel):
    image_url_parameter: ClassVar[str | None] = "image_url"
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
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


class Kling3ProImageToVideoModel(ImageToVideoModel):
    endpoint = "fal-ai/kling-video/o3/pro/image-to-video"
    display_name = "Kling 3.0 Pro"


class Wan21ImageToVideoModel(ImageToVideoModel):
    endpoint = "fal-ai/wan/v2.1/image-to-video"
    display_name = "Wan 2.1"
