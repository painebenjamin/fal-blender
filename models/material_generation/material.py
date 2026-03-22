from __future__ import annotations

from typing import Any

from ..base import VisualFalModel


class MaterialGenerationModel(VisualFalModel):
    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        params = super().parameters(**kwargs)
        for key in ("output_format", "tiling_mode"):
            if key in kwargs:
                params[key] = kwargs[key]
        return params


class PatinaMaterialGenerationModel(MaterialGenerationModel):
    endpoint = "PATINA/material"
    display_name = "Patina Material"
    prompt_expansion_parameter = "enable_prompt_expansion"
