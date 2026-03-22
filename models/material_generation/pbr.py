from __future__ import annotations

from typing import Any

from ..base import VisualFalModel


class PBREstimationModel(VisualFalModel):
    """Base model for PBR material map estimation from images."""

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build API parameters, forwarding an optional output format."""
        params = super().parameters(**kwargs)
        if "output_format" in kwargs:
            params["output_format"] = kwargs["output_format"]
        return params


class PatinaPBREstimationModel(PBREstimationModel):
    """Patina PBR estimation model."""

    endpoint = "PATINA/patina"
    display_name = "Patina"
