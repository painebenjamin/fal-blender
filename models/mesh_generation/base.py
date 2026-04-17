from __future__ import annotations

from typing import Any, ClassVar

from ...utils import path_to_data_uri
from ..base import FalModel

__all__ = [
    "MeshyV6PreviewModel",
]


class MeshGenerationModel(FalModel):
    """Base model for mesh generation."""

    image_url_parameter: ClassVar[str | None] = None
    image_urls_parameter: ClassVar[str | None] = None
    generate_materials_parameter: ClassVar[str | None] = None
    enable_prompt_expansion_parameter: ClassVar[str | None] = None
    prompt_parameter: ClassVar[str | None] = "prompt"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build the API parameters from static defaults and an optional image path."""
        params = super().parameters(**kwargs)

        image_paths = []
        image_urls = []

        if "image_paths" in kwargs:
            image_paths = kwargs["image_paths"]
        if "image_path" in kwargs:
            image_paths.append(kwargs["image_path"])
        if "image_urls" in kwargs:
            image_urls = kwargs["image_urls"]
        if "image_url" in kwargs:
            image_urls.append(kwargs["image_url"])

        if cls.image_urls_parameter or cls.image_url_parameter:
            all_image_urls = image_urls + [
                path_to_data_uri(image_path) for image_path in image_paths
            ]
            if all_image_urls:
                if cls.image_urls_parameter:
                    params[cls.image_urls_parameter] = all_image_urls
                if cls.image_url_parameter:
                    params[cls.image_url_parameter] = all_image_urls[0]

        if cls.generate_materials_parameter:
            params[cls.generate_materials_parameter] = kwargs.get(
                "generate_materials", True
            )

        if cls.prompt_parameter:
            params["prompt"] = kwargs.get("prompt", "")

        if cls.enable_prompt_expansion_parameter:
            params[cls.enable_prompt_expansion_parameter] = kwargs.get(
                "enable_prompt_expansion", True
            )

        return params


class MeshyV6PreviewModel(FalModel):
    display_name = "Meshy v6 Preview"
    static_parameters = {
        "should_remesh": False,
        "should_texture": True,
        "topology": "triangle",
    }
    image_url_parameter = "image_url"
    generate_materials_parameter = "generate_pbr"


class Hunyuan3DV31ProModel(FalModel):
    display_name = "Hunyuan 3D v3.1 Pro"
    image_url_parameter = "input_image_url"
    generate_materials_parameter = "generate_pbr"


class Hunyuan3DV31RapidModel(FalModel):
    display_name = "Hunyuan 3D v3.1 Rapid"
    image_url_parameter = "input_image_url"
    generate_materials_parameter = "generate_pbr"


class TripoP1Model(FalModel):
    """Tripo P1 model base."""
    display_name = "Tripo P1"
    image_url_parameter = "image_url"
    static_parameters: ClassVar[dict[str, Any]] = {"texture": True}


class TripoH31Model(FalModel):
    """Tripo H3.1 model base."""
    display_name = "Tripo H3.1"
    image_url_parameter = "image_url"
    generate_materials_parameter = "pbr"
    static_parameters: ClassVar[dict[str, Any]] = {"texture": True, "pbr": True}
