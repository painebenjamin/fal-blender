from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, ClassVar

from ..utils import path_to_data_uri


class FalModel(metaclass=ABCMeta):
    enabled: ClassVar[bool] = True
    endpoint: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str] = ""
    static_parameters: ClassVar[dict[str, Any]] = {}

    @classmethod
    @abstractmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        pass

    @classmethod
    def catalog(cls) -> dict[str, FalModel]:
        """
        Returns a dictionary of all available models.
        """
        catalog: dict[str, type[FalModel]] = {}
        for subcls in cls.__subclasses__():
            catalog[subcls.__name__] = subcls
        return catalog

    @classmethod
    def is_available(cls) -> bool:
        """
        Returns True if the model is available.
        """
        return (
            getattr(cls, "endpoint", None) is not None
            and getattr(cls, "display_name", None) is not None
            and getattr(cls, "enabled", True)
        )

    @classmethod
    def enumerate(cls, **kwargs: Any) -> list[tuple[str, str, str]]:
        """
        Returns a list of all available models.
        """
        return [
            (subcls.__name__, subcls.display_name, subcls.description)
            for subcls in cls.__subclasses__()
            if subcls.is_available()
        ]


class VisualFalModel(FalModel):
    use_resolution_aspect_ratio: ClassVar[bool] = False
    aspect_ratios: ClassVar[list[str]] = []
    resolutions: ClassVar[dict[str, int]] = {}
    size_parameter: ClassVar[str | None] = None
    modulo: ClassVar[int | None] = None
    image_urls_parameter: ClassVar[str | None] = None
    image_url_parameter: ClassVar[str | None] = None
    video_urls_parameter: ClassVar[str | None] = None
    video_url_parameter: ClassVar[str | None] = None
    prompt_expansion_parameter: ClassVar[str | None] = None

    @classmethod
    def _to_resolution_aspect_ratio(cls, width: int, height: int) -> tuple[str, str]:
        """
        Convert pixel dimensions to closest aspect ratio + resolution tier.
        """
        if not cls.aspect_ratios:
            raise RuntimeError(
                f"No aspect ratios defined for {cls.__name__}; either disable `use_resolution_aspect_ratio` or define the aspect ratios in the model class."
            )
        if not cls.resolutions:
            raise RuntimeError(
                f"No resolutions defined for {cls.__name__}; either disable `use_resolution_aspect_ratio` or define the resolutions in the model class."
            )

        target_ratio = width / height
        best_ar = cls.aspect_ratios[0]
        best_diff = float("inf")

        for ar in cls.aspect_ratios:
            try:
                w, h = map(int, ar.split(":"))
            except ValueError as e:
                warnings.warn(f"Invalid aspect ratio {ar} for {cls.__name__}: {e}")
                continue

            diff = abs(target_ratio - w / h)
            if diff < best_diff:
                best_diff = diff
                best_ar = ar

        longest = max(width, height)
        best_res = next(iter(cls.resolutions.keys()))
        best_res_diff = float("inf")

        for name, pixels in cls.resolutions.items():
            diff = abs(longest - pixels)
            if diff < best_res_diff:
                best_res_diff = diff
                best_res = name

        return best_ar, best_res

    @classmethod
    def _get_size_parameters(cls, width: int, height: int) -> dict[str, Any]:
        """
        Returns the size parameters for the model.
        """
        if cls.use_resolution_aspect_ratio:
            aspect_ratio, resolution = cls._to_resolution_aspect_ratio(width, height)
            return {
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            }

        if cls.modulo:
            width = width // cls.modulo * cls.modulo
            height = height // cls.modulo * cls.modulo

        if cls.size_parameter:
            return {
                cls.size_parameter: {"width": width, "height": height},
            }

        return {
            "width": width,
            "height": height,
        }

    @classmethod
    def _get_image_urls_parameters(
        cls,
        image_paths: list[str] | None = None,
        image_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Returns the image urls parameters for the model.
        """
        if not cls.image_urls_parameter and not cls.image_url_parameter:
            return {}

        image_uris = []
        if image_paths:
            for image_path in image_paths:
                image_uris.append(path_to_data_uri(image_path))
        if image_urls:
            image_uris.extend(image_urls)

        if cls.image_urls_parameter:
            return {
                cls.image_urls_parameter: image_uris,
            }

        return {
            cls.image_url_parameter: image_uris[0] if image_uris else None,
        }

    @classmethod
    def _get_video_urls_parameters(
        cls,
        video_paths: list[str] | None = None,
        video_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Returns the video urls parameters for the model.
        """
        if not cls.video_urls_parameter and not cls.video_url_parameter:
            return {}

        video_uris = []
        if video_paths:
            for video_path in video_paths:
                video_uris.append(path_to_data_uri(video_path))
        if video_urls:
            video_uris.extend(video_urls)

        if cls.video_urls_parameter:
            return {
                cls.video_urls_parameter: video_uris,
            }
        return {
            cls.video_url_parameter: video_uris[0] if video_uris else None,
        }

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        width = kwargs.get("width", 1024)
        height = kwargs.get("height", 1024)
        seed = kwargs.get("seed", None)
        prompt = kwargs.get("prompt", None)
        enable_prompt_expansion = kwargs.get("enable_prompt_expansion", True)

        image_paths: list[str] = []
        image_urls: list[str] = []
        if "image_paths" in kwargs:
            image_paths = kwargs["image_paths"]
        if "image_path" in kwargs:
            image_paths.append(kwargs["image_path"])
        if "image_urls" in kwargs:
            image_urls = kwargs["image_urls"]
        if "image_url" in kwargs:
            image_urls.append(kwargs["image_url"])

        video_paths: list[str] = []
        video_urls: list[str] = []
        if "video_paths" in kwargs:
            video_paths = kwargs["video_paths"]
        if "video_path" in kwargs:
            video_paths.append(kwargs["video_path"])
        if "video_urls" in kwargs:
            video_urls = kwargs["video_urls"]
        if "video_url" in kwargs:
            video_urls.append(kwargs["video_url"])

        params: dict[str, Any] = {}
        params.update(cls._get_size_parameters(width, height))
        params.update(cls._get_image_urls_parameters(image_paths, image_urls))
        params.update(cls._get_video_urls_parameters(video_paths, video_urls))

        if seed:
            params["seed"] = seed
        if prompt:
            params["prompt"] = prompt
        if cls.prompt_expansion_parameter:
            params[cls.prompt_expansion_parameter] = enable_prompt_expansion

        return params
