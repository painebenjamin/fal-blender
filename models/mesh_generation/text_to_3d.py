from __future__ import annotations

from typing import Any, ClassVar

from ..base import FalModel

__all__ = [
    "TextTo3DModel",
    "MeshyV6TextTo3DModel",
]


class TextTo3DModel(FalModel):
    prompt_expansion_parameter: ClassVar[str | None] = "enable_prompt_expansion"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = dict(cls.static_parameters)
        prompt = kwargs.get("prompt", "")
        if prompt:
            params["prompt"] = prompt
        if cls.prompt_expansion_parameter:
            params[cls.prompt_expansion_parameter] = kwargs.get(
                "enable_prompt_expansion", True
            )
        return params


class MeshyV6TextTo3DModel(TextTo3DModel):
    endpoint = "fal-ai/meshy/v6/text-to-3d"
    display_name = "Meshy v6"
