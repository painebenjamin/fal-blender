from __future__ import annotations

from typing import Any

from ..base import VisualFalModel


class PBREstimationModel(VisualFalModel):
    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        params = super().parameters(**kwargs)
        if "output_format" in kwargs:
            params["output_format"] = kwargs["output_format"]
        return params


class PatinaPBREstimationModel(PBREstimationModel):
    endpoint = "PATINA/patina"
    display_name = "Patina"
