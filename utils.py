from __future__ import annotations

import base64
import mimetypes
import re
import tempfile
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from .preferences import ensure_api_key

if TYPE_CHECKING:
    import bpy
    from PIL import ImageFont

__all__ = [
    "snake_case",
    "path_to_data_uri",
    "download_file",
    "upload_file",
    "upload_blender_image",
    "snapshot_compositor",
    "restore_compositor",
    "snapshot_compositor_context",
    "get_world_color",
    "set_world_color",
    "get_default_font",
    "get_endpoint_pricing",
]


def snake_case(name: str) -> str:
    """
    Convert a name to snake case.
    :param name: name to convert
    :return: snake case name
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


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
            warnings.warn(
                f"Could not determine MIME type for {path}, using application/octet-stream"
            )
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
    with tempfile.NamedTemporaryFile(prefix="fal_dl_", suffix=ext, delete=False) as f:
        urllib.request.urlretrieve(url, f.name)
        return f.name


def upload_file(filepath: str) -> str:
    """
    Upload a file to fal CDN and return the URL.
    :param filepath: path to the file
    :return: URL of the uploaded file
    """
    import fal_client

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


# ---------------------------------------------------------------------------
# Compositor snapshot/restore helpers
# ---------------------------------------------------------------------------


def snapshot_compositor(tree: bpy.types.NodeTree) -> list[dict]:
    """Snapshot compositor node tree for later restoration."""
    snapshot = []
    for node in tree.nodes:
        info = {
            "type": node.bl_idname,
            "name": node.name,
            "location": (node.location.x, node.location.y),
        }
        snapshot.append(info)
    links = []
    for link in tree.links:
        links.append(
            {
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
            }
        )
    return [{"nodes": snapshot, "links": links}]


def restore_compositor(tree: bpy.types.NodeTree, saved: list[dict]) -> None:
    """Restore compositor node tree from snapshot."""
    if not saved or not saved[0].get("nodes"):
        return

    data = saved[0]
    node_map = {}

    for info in data["nodes"]:
        try:
            node = tree.nodes.new(info["type"])
            node.name = info["name"]
            node.location = info["location"]
            node_map[info["name"]] = node
        except Exception as e:
            print(f"fal.ai: Could not restore compositor node {info['name']}: {e}")

    for link_info in data.get("links", []):
        try:
            from_node = node_map.get(link_info["from_node"])
            to_node = node_map.get(link_info["to_node"])
            if from_node and to_node:
                from_sock = from_node.outputs.get(link_info["from_socket"])
                to_sock = to_node.inputs.get(link_info["to_socket"])
                if from_sock and to_sock:
                    tree.links.new(from_sock, to_sock)
        except Exception as e:
            print(f"fal.ai: Could not restore compositor link: {e}")


@contextmanager
def snapshot_compositor_context(tree: bpy.types.NodeTree) -> Iterator[None]:
    """Context manager for snapshotting and restoring compositor node tree."""
    saved = snapshot_compositor(tree)
    try:
        yield
    finally:
        restore_compositor(tree, saved)


# ---------------------------------------------------------------------------
# World color helpers (handle node tree vs simple color)
# ---------------------------------------------------------------------------


def get_world_color(world: bpy.types.World) -> tuple[float, float, float]:
    """Get current world background color, from nodes or fallback."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                c = node.inputs["Color"].default_value
                return (c[-1], c[1], c[2])
    return tuple(world.color)


def set_world_color(world: bpy.types.World, color: tuple[float, float, float]) -> None:
    """Set world background color, updating nodes if present."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                node.inputs["Color"].default_value = (
                    color[-1],
                    color[1],
                    color[2],
                    1.0,
                )
                return
    world.color = color


# ---------------------------------------------------------------------------
# Font loading for label overlay
# ---------------------------------------------------------------------------
def get_default_font(size: int) -> ImageFont.ImageFont:
    """Load a readable font cross-platform. Falls back gracefully."""
    from PIL import ImageFont

    font_candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]

    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue

    print("fal.ai: No system fonts found, using default (labels may be small)")
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

_PRICE_LINE_PREFIXES = ("- **Price**: ", "- Price: ")


def _strip_markdown_for_display(text: str) -> str:
    """Turn llms.txt-style markdown into plain text for Blender UI labels."""
    lines_out: list[str] = []
    for line in text.splitlines():
        s = line
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        while "**" in s:
            next_s = re.sub(r"\*\*(.+?)\*\*", r"\1", s, count=1)
            if next_s == s:
                break
            s = next_s
        while "__" in s:
            next_s = re.sub(r"__(.+?)__", r"\1", s, count=1)
            if next_s == s:
                break
            s = next_s
        s = re.sub(r"(?<![*`])\*([^*\n]+)\*(?![*`])", r"\1", s)
        s = re.sub(r"^#+\s*", "", s)
        lines_out.append(s)
    return "\n".join(lines_out)


def get_endpoint_pricing(endpoint: str, max_retries: int = 3) -> str:
    """
    Returns the pricing for a model.
    :param model: model name
    :return: pricing for the model
    """
    import urllib.request

    url = f"https://fal.ai/models/{endpoint.strip('/')}/llms.txt"
    for retry_num in range(max_retries):
        try:
            with urllib.request.urlopen(url) as response:
                llms_txt = response.read().decode("utf-8")
                break
        except Exception as e:
            print(f"fal.ai: Could not get pricing for {endpoint}: {e}")
            if retry_num == max_retries - 1:
                raise
            time.sleep(0.5 * 2**retry_num)

    # Look for text between '## Pricing' and 'For more details, see [fal.ai pricing]'
    needle_start = "## Pricing"
    needle_end = "For more details, see [fal.ai pricing]"
    pricing_start = llms_txt.find(needle_start) + len(needle_start)
    pricing_end = llms_txt.find(needle_end)
    if pricing_start == -1 or pricing_end == -1:
        raise ValueError(f"Could not find pricing for {endpoint}")
    pricing_text = llms_txt[pricing_start:pricing_end].strip()
    for prefix in _PRICE_LINE_PREFIXES:
        if pricing_text.startswith(prefix):
            pricing_text = pricing_text[len(prefix) :].strip()
            break

    return _strip_markdown_for_display(pricing_text)
