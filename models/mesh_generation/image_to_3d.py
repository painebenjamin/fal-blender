from __future__ import annotations

from typing import Any

from ..base import FalModel

__all__ = [
    "ImageTo3DModel",
    "MeshyV6ImageTo3DModel",
    "MeshyV5ImageTo3DModel",
]


class ImageTo3DModel(FalModel):
    """Base model for image-to-3D mesh generation."""

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build the API parameters from static defaults and an optional image URL."""
        params: dict[str, Any] = dict(cls.static_parameters)
        image_url = kwargs.get("image_url")
        if image_url:
            params["image_url"] = image_url
        return params


class MeshyV6ImageTo3DModel(ImageTo3DModel):
    """Meshy v6 image-to-3D model."""

    endpoint = "fal-ai/meshy/v6/image-to-3d"
    display_name = "Meshy v6"


class MeshyV5ImageTo3DModel(ImageTo3DModel):
    """Meshy v5 image-to-3D model."""

    endpoint = "fal-ai/meshy/v5/image-to-3d"
    display_name = "Meshy v5"
