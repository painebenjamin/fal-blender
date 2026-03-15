from __future__ import annotations

import mimetypes
import fal_client
import base64
import warnings
import tempfile

from pathlib import Path
from typing import TYPE_CHECKING

from .preferences import ensure_api_key

if TYPE_CHECKING:
    import bpy

__all__ = [
    "path_to_data_uri",
    "download_file",
    "upload_file",
    "upload_blender_image",
]

def path_to_data_uri(path: str, mime_type: str | None = None) -> str:
    """
    Convert a file path to a data URI.
    :param path: path to the file
    :param mime_type: MIME type of the file
    :return: data URI of the file
    """
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            warnings.warn(f"Could not determine MIME type for {path}, using application/octet-stream")
            mime_type = "application/octet-stream"
    with open(path, "rb") as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"

def download_file(url: str, suffix: str = ".bin") -> str:
    """
    Download a URL to a temp file, return local path.
    :param url: URL of the file
    :param suffix: suffix of the file
    :return: local path of the downloaded file
    """
    import urllib.request

    ext = Path(url.split("?")[0]).suffix or suffix
    with tempfile.NamedTemporaryFile(
        prefix="fal_dl_", suffix=ext, delete=False
    ) as f:
        urllib.request.urlretrieve(url, f.name)
        return f.name

def upload_file(filepath: str) -> str:
    """
    Upload a file to fal CDN and return the URL.
    :param filepath: path to the file
    :return: URL of the uploaded file
    """
    ensure_api_key()
    url = fal_client.upload_file(filepath)
    print(f"fal.ai: Uploaded video {filepath} -> {url}")
    return url


def upload_blender_image(image: bpy.types.Image) -> str:
    """
    Save a Blender image to temp file and upload to fal CDN.
    :param image: bpy.types.Image instance
    :return: URL of the uploaded file
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        old_path = image.filepath_raw
        old_format = image.file_format
        image.filepath_raw = f.name
        image.file_format = "PNG"
        image.save()
        image.filepath_raw = old_path
        image.file_format = old_format
        return upload_file(f.name)