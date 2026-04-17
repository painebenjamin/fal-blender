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
    "Seedance20TextToVideoModel",
    "Seedance20FastTextToVideoModel",
    "KlingV3StandardTextToVideoModel",
    "KlingV3ProTextToVideoModel",
    "Veo31TextToVideoModel",
    "Veo31FastTextToVideoModel",
    "LTX23TextToVideoModel",
    "LTX23DistilledTextToVideoModel",
    "Wan27TextToVideoModel",
    "Sora2TextToVideoModel",
]


class TextToVideoModel(VisualFalModel):
    """Base model for text-to-video generation."""

    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for text-to-video generation."""
        params: dict[str, Any] = super().parameters(**kwargs)
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


class Seedance20TextToVideoModel(TextToVideoModel):
    """Seedance 2.0 text-to-video model."""

    display_name = "Seedance 2.0"
    endpoint = "bytedance/seedance-2.0/text-to-video"


class Seedance20FastTextToVideoModel(TextToVideoModel):
    """Seedance 2.0 Fast text-to-video model."""

    display_name = "Seedance 2.0 Fast"
    endpoint = "bytedance/seedance-2.0/fast/text-to-video"


class KlingV3StandardTextToVideoModel(TextToVideoModel):
    """Kling v3 Standard text-to-video model."""

    display_name = "Kling v3 Standard"
    endpoint = "fal-ai/kling-video/v3/standard/text-to-video"


class KlingV3ProTextToVideoModel(TextToVideoModel):
    """Kling v3 Pro text-to-video model."""

    display_name = "Kling v3 Pro"
    endpoint = "fal-ai/kling-video/v3/pro/text-to-video"


class Veo31TextToVideoModel(TextToVideoModel):
    """Veo 3.1 text-to-video model."""

    display_name = "Veo 3.1"
    endpoint = "fal-ai/veo3.1"


class Veo31FastTextToVideoModel(TextToVideoModel):
    """Veo 3.1 Fast text-to-video model."""

    display_name = "Veo 3.1 Fast"
    endpoint = "fal-ai/veo3.1/fast"


class LTX23TextToVideoModel(TextToVideoModel):
    """LTX 2.3 22B text-to-video model."""

    display_name = "LTX 2.3 22B"
    endpoint = "fal-ai/ltx-2.3-22b/text-to-video"


class LTX23DistilledTextToVideoModel(TextToVideoModel):
    """LTX 2.3 22B Distilled text-to-video model."""

    display_name = "LTX 2.3 22B Distilled"
    endpoint = "fal-ai/ltx-2.3-22b/distilled/text-to-video"


class Wan27TextToVideoModel(TextToVideoModel):
    """Wan 2.7 text-to-video model."""

    display_name = "Wan 2.7"
    endpoint = "fal-ai/wan/v2.7/text-to-video"


class Sora2TextToVideoModel(TextToVideoModel):
    """Sora 2 text-to-video model."""

    display_name = "Sora 2"
    endpoint = "fal-ai/sora-2/text-to-video"
