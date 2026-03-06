# SPDX-License-Identifier: Apache-2.0
"""Endpoint registry — manually composed lists per feature category.

This is the SINGLE SOURCE OF TRUTH for which endpoints appear in each
feature's dropdown. Add/remove entries here to update the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ResolutionMode(Enum):
    """How the endpoint accepts resolution parameters."""

    PIXELS = auto()  # width/height in pixels (mod 16)
    ASPECT_RESOLUTION = auto()  # aspect_ratio + resolution tier


@dataclass(frozen=True)
class EndpointDef:
    """A fal endpoint available for a feature."""

    endpoint_id: str
    display_name: str
    resolution_mode: ResolutionMode = ResolutionMode.PIXELS
    default_params: dict = field(default_factory=dict)
    supports_seed: bool = True
    notes: str = ""


# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------
IMAGE_GENERATION_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/nano-banana-pro",
        "Nano Banana Pro",
        resolution_mode=ResolutionMode.ASPECT_RESOLUTION,
    ),
    EndpointDef(
        "fal-ai/nano-banana-2",
        "Nano Banana 2",
        resolution_mode=ResolutionMode.ASPECT_RESOLUTION,
    ),
    EndpointDef(
        "fal-ai/flux/dev",
        "FLUX.1 [dev]",
        resolution_mode=ResolutionMode.PIXELS,
    ),
    EndpointDef(
        "fal-ai/z-image/turbo",
        "z-image Turbo",
        resolution_mode=ResolutionMode.PIXELS,
    ),
]

# ---------------------------------------------------------------------------
# Tiled Texture Generation
# ---------------------------------------------------------------------------
TILING_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "painebenjamin/z-image-turbo-seamless-tiling",
        "Z-Image Turbo Seamless Tiling",
        resolution_mode=ResolutionMode.PIXELS,
        default_params={"tile_size": 64, "tile_stride": 32},
        notes="Generates seamlessly tileable textures via multi-diffusion",
    ),
]

# ---------------------------------------------------------------------------
# PBR Material (texture -> basecolor/normal/roughness/metalness)
# ---------------------------------------------------------------------------
PBR_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "painebenjamin/chord-pbr",
        "CHORD PBR (Ubisoft)",
        resolution_mode=ResolutionMode.PIXELS,
        supports_seed=False,
        notes="Estimates PBR maps from a single texture image (research-only)",
    ),
]

# ---------------------------------------------------------------------------
# Depth-Controlled Image Generation
# ---------------------------------------------------------------------------
DEPTH_CONTROL_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/flux-control-lora-depth/image-to-image",
        "FLUX Depth ControlNet",
    ),
    EndpointDef(
        "fal-ai/z-image/turbo/controlnet",
        "z-image ControlNet",
        notes="Fast, good for iterative workflows",
    ),
    EndpointDef(
        "fal-ai/flux-general",
        "FLUX General (multi-ControlNet)",
        notes="Supports combining depth + other controls",
    ),
]

# ---------------------------------------------------------------------------
# 3D Generation
# ---------------------------------------------------------------------------
TEXT_TO_3D_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/meshy/v6/text-to-3d", "Meshy v6 Text-to-3D"),
]

IMAGE_TO_3D_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/meshy/v6/image-to-3d", "Meshy v6 Image-to-3D"),
    EndpointDef("fal-ai/meshy/v5/image-to-3d", "Meshy v5 Image-to-3D"),
]

MULTI_IMAGE_TO_3D_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/meshy/v5/multi-image-to-3d", "Meshy v5 Multi-Image-to-3D"
    ),
]

# ---------------------------------------------------------------------------
# 3D-to-3D (Retexture, Remesh)
# ---------------------------------------------------------------------------
RETEXTURE_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/meshy/v5/retexture", "Meshy v5 Retexture"),
]

REMESH_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/meshy/v5/remesh", "Meshy v5 Remesh"),
]

# ---------------------------------------------------------------------------
# Multi-Angle Image Generation
# ---------------------------------------------------------------------------
MULTI_ANGLE_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/qwen-image-edit-2511-multiple-angles",
        "Qwen Multi-Angle",
    ),
]

# ---------------------------------------------------------------------------
# AI Upscale
# ---------------------------------------------------------------------------
UPSCALE_IMAGE_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/seedvr/upscale/image", "SeedVR2 Image Upscale"),
    EndpointDef("fal-ai/aura-sr", "AuraSR"),
    EndpointDef("fal-ai/clarity-upscaler", "Clarity Upscaler"),
]

UPSCALE_VIDEO_ENDPOINTS: list[EndpointDef] = [
    EndpointDef("fal-ai/seedvr/upscale/video", "SeedVR2 Video Upscale"),
]

# ---------------------------------------------------------------------------
# Video Generation
# ---------------------------------------------------------------------------
TEXT_TO_VIDEO_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/kling-video/o3/pro/text-to-video",
        "Kling 3.0 Pro Text-to-Video",
    ),
    EndpointDef(
        "fal-ai/wan/v2.1/text-to-video", "Wan 2.1 Text-to-Video"
    ),
]

IMAGE_TO_VIDEO_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/kling-video/o3/pro/image-to-video",
        "Kling 3.0 Pro Image-to-Video",
    ),
    EndpointDef(
        "fal-ai/wan/v2.1/image-to-video", "Wan 2.1 Image-to-Video"
    ),
]

DEPTH_VIDEO_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/ltx-2-19b/video-to-video",
        "LTX-2 19B (Depth)",
        default_params={"ic_lora": "depth"},
        notes="Depth-conditioned video generation via IC-LoRA",
    ),
    EndpointDef(
        "fal-ai/wan-vace-14b/depth",
        "Wan-VACE 14B (Depth)",
        notes="Depth-conditioned video generation",
    ),
    EndpointDef(
        "fal-ai/wan-22-vace-fun-a14b/depth",
        "Wan-Fun 2.2 A14B (Depth)",
        notes="Depth-conditioned video generation",
    ),
]

# ---------------------------------------------------------------------------
# Audio Generation
# ---------------------------------------------------------------------------
TTS_ENDPOINTS: list[EndpointDef] = [
    # TODO: Populate with available TTS endpoints
]

SFX_ENDPOINTS: list[EndpointDef] = [
    # TODO: Populate with available SFX endpoints
]

MUSIC_ENDPOINTS: list[EndpointDef] = [
    # TODO: Populate with available music endpoints
]

# ---------------------------------------------------------------------------
# Vectorization
# ---------------------------------------------------------------------------
VECTORIZE_ENDPOINTS: list[EndpointDef] = [
    EndpointDef(
        "fal-ai/image2svg",
        "fal image2svg",
        notes="Cloud-based vectorization",
    ),
]

# ---------------------------------------------------------------------------
# Realtime (stretch goal)
# ---------------------------------------------------------------------------
REALTIME_ENDPOINTS: list[EndpointDef] = [
    # EndpointDef("fal-ai/flux-klein-realtime", "FLUX Klein Realtime"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def endpoint_items(
    endpoints: list[EndpointDef],
) -> list[tuple[str, str, str]]:
    """Convert endpoint list to Blender EnumProperty items.

    Returns list of (identifier, name, description) tuples.
    """
    return [
        (ep.endpoint_id, ep.display_name, ep.notes or ep.display_name)
        for ep in endpoints
    ]


def get_endpoint(
    endpoints: list[EndpointDef], endpoint_id: str
) -> EndpointDef | None:
    """Look up an endpoint definition by ID."""
    for ep in endpoints:
        if ep.endpoint_id == endpoint_id:
            return ep
    return None


# ---------------------------------------------------------------------------
# Resolution Helpers
# ---------------------------------------------------------------------------

ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21",
    "3:2", "2:3", "4:5", "5:4", "16:21", "21:16",
]

RESOLUTION_TIERS = {
    "0.5K": 512,
    "1K": 1024,
    "2K": 2048,
    "4K": 4096,
}


def pixels_to_aspect_resolution(
    width: int, height: int
) -> tuple[str, str]:
    """Convert pixel dimensions to closest aspect ratio + resolution tier."""
    target_ratio = width / height

    best_ar = "1:1"
    best_diff = float("inf")
    for ar in ASPECT_RATIOS:
        w, h = map(int, ar.split(":"))
        diff = abs(target_ratio - w / h)
        if diff < best_diff:
            best_diff = diff
            best_ar = ar

    longest = max(width, height)
    best_res = "1K"
    best_res_diff = float("inf")
    for name, pixels in RESOLUTION_TIERS.items():
        diff = abs(longest - pixels)
        if diff < best_res_diff:
            best_res_diff = diff
            best_res = name

    return best_ar, best_res


def snap_to_mod16(width: int, height: int) -> tuple[int, int]:
    """Snap dimensions to nearest multiple of 16."""
    return (
        max(16, round(width / 16) * 16),
        max(16, round(height / 16) * 16),
    )


def register():
    pass


def unregister():
    pass
