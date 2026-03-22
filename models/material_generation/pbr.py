from __future__ import annotations

from typing import Any

from ..base import FalModel


class PBREstimationModel(FalModel):
    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if "image_url" in kwargs:
            params["image_url"] = kwargs["image_url"]
        if "output_format" in kwargs:
            params["output_format"] = kwargs["output_format"]
        return params


class PatinaPBREstimationModel(PBREstimationModel):
    endpoint = "PATINA/patina"
    display_name = "Patina"
