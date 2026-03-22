from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel

__all__ = [
    "TextToVideoModel",
    "Kling3ProTextToVideoModel",
    "Wan21TextToVideoModel",
]


class TextToVideoModel(VisualFalModel):
    """Base model for text-to-video generation."""

    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for text-to-video generation."""
        params: dict[str, Any] = dict(cls.static_parameters)
        prompt = kwargs.get("prompt", "")
        if prompt:
            params["prompt"] = prompt
        enable = kwargs.get("enable_prompt_expansion", True)
        params["enable_prompt_expansion"] = enable
        params["expand_prompt"] = enable
        duration = kwargs.get("duration")
        if duration:
            params["duration"] = duration
        return params


class Kling3ProTextToVideoModel(TextToVideoModel):
    """Kling 3.0 Pro text-to-video model."""

    endpoint = "fal-ai/kling-video/o3/pro/text-to-video"
    display_name = "Kling 3.0 Pro"


class Wan21TextToVideoModel(TextToVideoModel):
    """Wan 2.1 text-to-video model."""

    endpoint = "fal-ai/wan/v2.1/text-to-video"
    display_name = "Wan 2.1"
