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
    "TextToVideoModel",
    "Wan22TextToVideoModel",
    "Wan22TurboTextToVideoModel",
    "LTX2TextToVideoModel",
    "LTX2DistilledTextToVideoModel",
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


class Wan22TextToVideoModel(TextToVideoModel, Wan22VideoModel):
    """Wan 2.2 text-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/text-to-video"


class Wan22TurboTextToVideoModel(TextToVideoModel, Wan22TurboVideoModel):
    """Wan 2.2 turbo text-to-video model."""

    endpoint = "fal-ai/wan/v2.2-a14b/text-to-video/turbo"


class LTX2TextToVideoModel(TextToVideoModel, LTX2VideoModel):
    """LTX-2 19B text-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/text-to-video"


class LTX2DistilledTextToVideoModel(TextToVideoModel, LTX2DistilledVideoModel):
    """LTX-2 19B distilled text-to-video model."""

    endpoint = "fal-ai/ltx-2-19b/distilled/text-to-video"
