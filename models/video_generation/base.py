from ..base import VisualFalModel

__all__ = [
    "LTX2VideoModel",
    "LTX2DistilledVideoModel",
    "Wan22VideoModel",
    "Wan22TurboVideoModel",
    "WanVACE14BVideoModel",
    "WanFun22A14BVideoModel",
]


class LTX2VideoModel(VisualFalModel):
    """Base model for LTX 2 video generation."""

    display_name = "LTX-2 19B"
    size_parameter = "video_size"


class LTX2DistilledVideoModel(LTX2VideoModel):
    """LTX 2.0 distilled video model."""

    display_name = "LTX-2 19B Distilled"
    size_parameter = "video_size"


class Wan22VideoModel(VisualFalModel):
    """Wan 2.2 video model."""

    display_name = "Wan 2.2"


class Wan22TurboVideoModel(Wan22VideoModel):
    """Wan 2.2 turbo video model."""

    display_name = "Wan 2.2 Turbo"


class WanVACE14BVideoModel(VisualFalModel):
    """Wan-VACE 14B video model."""

    display_name = "Wan-VACE 14B"


class WanFun22A14BVideoModel(VisualFalModel):
    """Wan-Fun 2.2 A14B video model."""

    display_name = "Wan Fun 2.2 A14B"
