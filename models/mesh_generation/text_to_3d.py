from __future__ import annotations

from .base import (Hunyuan3DV31ProModel, Hunyuan3DV31RapidModel,
                   MeshGenerationModel, MeshyV6PreviewModel)

__all__ = [
    "TextTo3DModel",
    "MeshyV6PreviewTextTo3DModel",
    "Hunyuan3DV31ProTextTo3DModel",
    "Hunyuan3DV31RapidTextTo3DModel",
]


class TextTo3DModel(MeshGenerationModel):
    """Base model for text-to-3D mesh generation."""

    pass


class MeshyV6PreviewTextTo3DModel(TextTo3DModel, MeshyV6PreviewModel):
    """Meshy v6 preview text-to-3D model."""

    endpoint = "fal-ai/meshy/v6-preview/text-to-3d"


class Hunyuan3DV31ProTextTo3DModel(TextTo3DModel, Hunyuan3DV31ProModel):
    """Hunyuan 3D v3.1 Pro text-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/pro/text-to-3d"


class Hunyuan3DV31RapidTextTo3DModel(TextTo3DModel, Hunyuan3DV31RapidModel):
    """Hunyuan 3D v3.1 Rapid text-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/rapid/text-to-3d"
