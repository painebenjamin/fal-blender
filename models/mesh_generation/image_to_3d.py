from __future__ import annotations

from .base import (
    Hunyuan3DV31ProModel,
    Hunyuan3DV31RapidModel,
    MeshGenerationModel,
    MeshyV6PreviewModel,
)

__all__ = [
    "ImageTo3DModel",
    "MeshyV6PreviewImageTo3DModel",
    "Hunyuan3DV31ProImageTo3DModel",
    "Hunyuan3DV31RapidImageTo3DModel",
]


class ImageTo3DModel(MeshGenerationModel):
    """Base model for image-to-3D mesh generation."""

    pass


class MeshyV6PreviewImageTo3DModel(ImageTo3DModel, MeshyV6PreviewModel):
    """Meshy v6 preview image-to-3D model."""

    endpoint = "fal-ai/meshy/v6-preview/image-to-3d"


class Hunyuan3DV31ProImageTo3DModel(ImageTo3DModel, Hunyuan3DV31ProModel):
    """Hunyuan 3D v3.1 Pro image-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/pro/image-to-3d"


class Hunyuan3DV31RapidImageTo3DModel(ImageTo3DModel, Hunyuan3DV31RapidModel):
    """Hunyuan 3D v3.1 Rapid image-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/rapid/image-to-3d"
