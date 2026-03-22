from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel

__all__ = [
    "DepthVideoModel",
    "LTX219BDistilledDepthVideoModel",
    "LTX219BDepthVideoModel",
    "WanVACE14BDepthVideoModel",
    "WanFun22A14BDepthVideoModel",
]


class DepthVideoModel(VisualFalModel):
    """Base model for depth-conditioned video generation."""

    video_url_parameter: ClassVar[str | None] = "video_url"
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters for depth-conditioned video generation."""
        params: dict[str, Any] = dict(cls.static_parameters)
        prompt = kwargs.get("prompt", "")
        if prompt:
            params["prompt"] = prompt
        enable = kwargs.get("enable_prompt_expansion", True)
        params["enable_prompt_expansion"] = enable
        params["expand_prompt"] = enable

        video_url = kwargs.get("video_url")
        if video_url:
            params["video_url"] = video_url

        num_frames = kwargs.get("num_frames")
        if num_frames:
            params["num_frames"] = num_frames

        image_url = kwargs.get("image_url")
        if image_url:
            params["image_url"] = image_url

        resolution = kwargs.get("resolution")
        if resolution:
            params["resolution"] = resolution

        return params


class LTX219BDistilledDepthVideoModel(DepthVideoModel):
    """LTX-2 19B Distilled depth-conditioned video model."""

    endpoint = "fal-ai/ltx-2-19b/distilled/video-to-video"
    display_name = "LTX-2 19B Distilled"
    description = "Faster depth video — fewer steps, good for simple camera moves"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "depth"}


class LTX219BDepthVideoModel(DepthVideoModel):
    """LTX-2 19B depth-conditioned video model using IC-LoRA."""

    endpoint = "fal-ai/ltx-2-19b/video-to-video"
    display_name = "LTX-2 19B"
    description = "Depth-conditioned video generation via IC-LoRA"
    static_parameters: ClassVar[dict[str, Any]] = {"ic_lora": "depth"}


class WanVACE14BDepthVideoModel(DepthVideoModel):
    """Wan-VACE 14B depth-conditioned video model."""

    endpoint = "fal-ai/wan-vace-14b/depth"
    display_name = "Wan-VACE 14B"
    description = "Depth-conditioned video generation"


class WanFun22A14BDepthVideoModel(DepthVideoModel):
    """Wan-Fun 2.2 A14B depth-conditioned video model."""

    endpoint = "fal-ai/wan-22-vace-fun-a14b/depth"
    display_name = "Wan-Fun 2.2 A14B"
    description = "Depth-conditioned video generation"
