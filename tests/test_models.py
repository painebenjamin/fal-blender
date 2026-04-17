"""Unit tests for model parameter generation.
These tests don't require Blender — run with pytest.

Note: These tests mock the minimal VisualFalModel behavior
since the full models module requires Blender imports.
"""

import warnings
from typing import Any, ClassVar


# Minimal mock of VisualFalModel for testing. Mirrors models/base.py —
# keep them in sync when behavior changes.
class VisualFalModel:
    """Mock of VisualFalModel for unit testing."""

    use_resolution_aspect_ratio: ClassVar[bool] = False
    emit_aspect_ratio: ClassVar[bool] = True
    emit_resolution: ClassVar[bool] = True
    aspect_ratios: ClassVar[list[str]] = []
    resolutions: ClassVar[dict[str, int]] = {}
    size_parameter: ClassVar[str | None] = None
    modulo: ClassVar[int | None] = None

    @classmethod
    def _closest_aspect_ratio(cls, width: int, height: int) -> str:
        """Pick the nearest defined aspect ratio."""
        if not cls.aspect_ratios:
            raise RuntimeError(f"No aspect ratios defined for {cls.__name__}")
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
        return best_ar

    @classmethod
    def _closest_resolution(cls, width: int, height: int) -> str:
        """Smallest tier ≥ short-side target (5% tolerance); else largest."""
        if not cls.resolutions:
            raise RuntimeError(f"No resolutions defined for {cls.__name__}")
        shortest = min(width, height)
        threshold = shortest * 0.95
        eligible = [
            (name, pixels)
            for name, pixels in cls.resolutions.items()
            if pixels >= threshold
        ]
        if eligible:
            return min(eligible, key=lambda item: item[1])[0]
        return max(cls.resolutions.items(), key=lambda item: item[1])[0]

    @classmethod
    def _to_resolution_aspect_ratio(cls, width: int, height: int) -> tuple[str, str]:
        """Kept for the legacy test helper — delegates to the split methods."""
        return (
            cls._closest_aspect_ratio(width, height),
            cls._closest_resolution(width, height),
        )

    @classmethod
    def describe_output_size(cls, width: int, height: int) -> str:
        """Human-readable summary of the effective output size."""
        if cls.use_resolution_aspect_ratio:
            parts: list[str] = []
            if cls.emit_resolution and cls.resolutions:
                parts.append(cls._closest_resolution(width, height))
            if cls.emit_aspect_ratio and cls.aspect_ratios:
                parts.append(cls._closest_aspect_ratio(width, height))
            if parts:
                return " ".join(parts)
        if cls.modulo:
            width = width // cls.modulo * cls.modulo
            height = height // cls.modulo * cls.modulo
        return f"{width}x{height}"

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


class TestResolutionCeilingPreference:
    """Resolution selection should prefer the smallest tier ≥ target."""

    def test_1080p_picks_2k_over_1k(self):
        """1920x1080 on {1K, 2K}: 1K upscales a lot, 2K downscales slightly — pick 2K."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9"]
            resolutions = {"1K": 1024, "2K": 2048}

        assert TestModel._closest_resolution(1920, 1080) == "2K"

    def test_exact_1024_stays_on_1k(self):
        """1024 is an exact match — don't jump to 2K for zero benefit."""

        class TestModel(VisualFalModel):
            resolutions = {"1K": 1024, "2K": 2048}

        assert TestModel._closest_resolution(1024, 1024) == "1K"

    def test_small_overshoot_within_tolerance_stays(self):
        """1025 is 0.1% over 1024 — within tolerance, keep 1K."""

        class TestModel(VisualFalModel):
            resolutions = {"1K": 1024, "2K": 2048}

        assert TestModel._closest_resolution(1025, 1025) == "1K"

    def test_target_exceeds_all_tiers_falls_back_to_largest(self):
        """Wan 2.2 maxes at 720p; 1920x1080 must fall back to 720p."""

        class TestModel(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9"]
            resolutions = {"480p": 480, "580p": 580, "720p": 720}

        assert TestModel._closest_resolution(1920, 1080) == "720p"

    def test_shortest_side_drives_selection(self):
        """Portrait 720x1280 should use the 720 short-side, not 1280."""

        class TestModel(VisualFalModel):
            resolutions = {"1K": 1024, "2K": 2048}

        # shortest=720; threshold=684; both eligible; pick smallest=1K.
        assert TestModel._closest_resolution(720, 1280) == "1K"


class TestDescribeOutputSize:
    """describe_output_size should match what the API actually receives."""

    def test_aspect_ratio_and_resolution(self):
        """Models with both should report 'resolution aspect_ratio'."""

        class Wan(VisualFalModel):
            use_resolution_aspect_ratio = True
            aspect_ratios = ["16:9", "9:16"]
            resolutions = {"480p": 480, "720p": 720}

        assert Wan.describe_output_size(1920, 1080) == "720p 16:9"

    def test_modulo_rounded(self):
        """Modulo models should report the rounded dims, not the input."""

        class Flux(VisualFalModel):
            modulo = 64

        assert Flux.describe_output_size(1000, 500) == "960x448"

    def test_passthrough_when_no_mapping(self):
        """Without modulo, aspect, or resolution mapping, return WxH verbatim."""

        class Raw(VisualFalModel):
            pass

        assert Raw.describe_output_size(1280, 720) == "1280x720"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
