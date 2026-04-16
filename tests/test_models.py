"""Unit tests for model parameter generation.
These tests don't require Blender — run with pytest.

Note: These tests mock the minimal VisualFalModel behavior
since the full models module requires Blender imports.
"""

import warnings
from typing import Any, ClassVar


# Minimal mock of VisualFalModel for testing
class VisualFalModel:
    """Mock of VisualFalModel for unit testing."""

    use_resolution_aspect_ratio: ClassVar[bool] = False
    aspect_ratios: ClassVar[list[str]] = []
    resolutions: ClassVar[dict[str, int]] = {}
    size_parameter: ClassVar[str | None] = None
    modulo: ClassVar[int | None] = None

    @classmethod
    def _to_resolution_aspect_ratio(cls, width: int, height: int) -> tuple[str, str]:
        """Convert pixel dimensions to closest aspect ratio + resolution tier."""
        if not cls.aspect_ratios:
            raise RuntimeError(f"No aspect ratios defined for {cls.__name__}")
        if not cls.resolutions:
            raise RuntimeError(f"No resolutions defined for {cls.__name__}")

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
        """Returns the size parameters for the model."""
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


class TestResolutionMapping:
    """Test aspect ratio and resolution tier mapping."""

    def test_16_9_aspect_ratio(self):
        """1920x1080 should map to 16:9."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9", "4:3", "1:1", "9:16"]
            resolutions = {"1K": 1024, "2K": 2048}

        ar, res = TestModel._to_resolution_aspect_ratio(1920, 1080)
        assert ar == "16:9"
        assert res == "2K"  # 1920 is closer to 2048 than 1024

    def test_1280x720_maps_to_1k(self):
        """1280x720 should map to 1K (closer to 1024 than 2048)."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9", "4:3", "1:1"]
            resolutions = {"1K": 1024, "2K": 2048}

        ar, res = TestModel._to_resolution_aspect_ratio(1280, 720)
        assert ar == "16:9"
        assert res == "1K"  # |1280-1024|=256 < |1280-2048|=768

    def test_square_aspect_ratio(self):
        """1024x1024 should map to 1:1."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9", "4:3", "1:1", "9:16"]
            resolutions = {"1K": 1024}

        ar, res = TestModel._to_resolution_aspect_ratio(1024, 1024)
        assert ar == "1:1"
        assert res == "1K"

    def test_portrait_aspect_ratio(self):
        """720x1280 should map to 9:16."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9", "4:3", "1:1", "9:16"]
            resolutions = {"1K": 1024, "2K": 2048}

        ar, res = TestModel._to_resolution_aspect_ratio(720, 1280)
        assert ar == "9:16"
        assert res == "1K"


class TestModelParameters:
    """Test model parameter building."""

    def test_size_parameter_nested(self):
        """Models with size_parameter should nest width/height."""

        class TestModel(VisualFalModel):
            size_parameter = "video_size"

        params = TestModel._get_size_parameters(1280, 720)
        assert params == {"video_size": {"width": 1280, "height": 720}}

    def test_size_parameter_flat(self):
        """Models without size_parameter should use flat width/height."""

        class TestModel(VisualFalModel):
            size_parameter = None

        params = TestModel._get_size_parameters(1280, 720)
        assert params == {"width": 1280, "height": 720}

    def test_modulo_rounding(self):
        """Models with modulo should round dimensions."""

        class TestModel(VisualFalModel):
            modulo = 64

        params = TestModel._get_size_parameters(1000, 500)
        assert params == {"width": 960, "height": 448}  # Rounded to 64


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
