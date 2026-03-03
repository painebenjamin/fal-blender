# SPDX-License-Identifier: Apache-2.0
"""API helpers — resolution translation, image upload, common patterns."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass


def build_image_gen_args(
    endpoint_id: str,
    prompt: str,
    width: int,
    height: int,
    seed: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build arguments for an image generation endpoint,
    handling resolution mode translation."""
    from ..endpoints import (
        IMAGE_GENERATION_ENDPOINTS,
        TILING_ENDPOINTS,
        ResolutionMode,
        get_endpoint,
        pixels_to_aspect_resolution,
        snap_to_mod16,
    )

    ep = get_endpoint(IMAGE_GENERATION_ENDPOINTS, endpoint_id)
    if ep is None:
        ep = get_endpoint(TILING_ENDPOINTS, endpoint_id)

    args: dict[str, Any] = {"prompt": prompt}

    if ep and ep.resolution_mode == ResolutionMode.ASPECT_RESOLUTION:
        aspect, resolution = pixels_to_aspect_resolution(width, height)
        args["aspect_ratio"] = aspect
        args["resolution"] = resolution
    else:
        w, h = snap_to_mod16(width, height)
        args["width"] = w
        args["height"] = h

    if seed is not None:
        args["seed"] = seed

    # Merge endpoint defaults
    if ep and ep.default_params:
        for k, v in ep.default_params.items():
            args.setdefault(k, v)

    # Merge caller extras
    if extra:
        args.update(extra)

    return args


def resolve_endpoint(endpoint_id: str, args: dict[str, Any]) -> str:
    """Resolve the correct endpoint path based on arguments.

    Nano Banana models use /edit when image args are present, / (text-to-image)
    when they are not.
    """
    has_image = any(
        k in args
        for k in ("image_url", "image_urls", "control_image_url")
    )

    if "nano-banana" in endpoint_id:
        if has_image:
            # Strip any existing sub-path and add /edit
            base = endpoint_id.split("/")[0] + "/" + endpoint_id.split("/")[1]
            return f"{base}/edit"
        else:
            # Pure text-to-image — root endpoint
            base = endpoint_id.split("/")[0] + "/" + endpoint_id.split("/")[1]
            return base

    return endpoint_id


def upload_image_file(filepath: str) -> str:
    """Upload a local image file to fal CDN, return URL."""
    import fal_client

    from ..preferences import ensure_api_key

    ensure_api_key()
    return fal_client.upload_file(filepath)


def upload_video_file(filepath: str) -> str:
    """Upload a video file to fal CDN and return the URL."""
    import fal_client
    url = fal_client.upload_file(filepath)
    print(f"fal.ai: Uploaded video {filepath} -> {url}")
    return url


def upload_blender_image(image) -> str:
    """Save a Blender image to temp file and upload to fal CDN.

    Args:
        image: bpy.types.Image instance
    """
    import fal_client

    from ..preferences import ensure_api_key

    ensure_api_key()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        old_path = image.filepath_raw
        old_format = image.file_format
        image.filepath_raw = f.name
        image.file_format = "PNG"
        image.save()
        image.filepath_raw = old_path
        image.file_format = old_format
        return fal_client.upload_file(f.name)


def upload_mesh_as_glb(obj) -> str:
    """Export a Blender object as GLB and upload to fal CDN.

    Args:
        obj: bpy.types.Object instance
    """
    import bpy  # type: ignore[import-not-found]
    import fal_client

    from ..preferences import ensure_api_key

    ensure_api_key()

    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        # Select only the target object
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.export_scene.gltf(
            filepath=f.name,
            use_selection=True,
            export_format="GLB",
        )
        return fal_client.upload_file(f.name)


def download_file(url: str, suffix: str = ".bin") -> str:
    """Download a URL to a temp file, return local path."""
    import urllib.request

    ext = Path(url.split("?")[0]).suffix or suffix
    with tempfile.NamedTemporaryFile(
        prefix="fal_dl_", suffix=ext, delete=False
    ) as f:
        urllib.request.urlretrieve(url, f.name)
        return f.name
