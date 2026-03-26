from __future__ import annotations

from typing import Any

import bpy

__all__ = [
    "apply_texture_to_object",
    "import_image_as_texture",
    "import_glb",
    "import_obj",
    "resize_image_to_target",
    "import_image_to_editor",
    "add_audio_to_vse",
    "add_video_to_vse",
]


def import_image_as_texture(
    image_path: str,
    *,
    name: str = "fal_texture",
    apply_to_selected: bool = True,
) -> bpy.types.Image:
    """Load an image file as a Blender Image datablock.

    Optionally applies it as the base color texture on the active
    object's material.
    """
    img = bpy.data.images.load(image_path)
    img.name = name

    if apply_to_selected and bpy.context.active_object:
        obj = bpy.context.active_object
        apply_texture_to_object(obj, img)

    return img


def apply_texture_to_object(obj: bpy.types.Object, img: bpy.types.Image) -> None:
    """Create or update a Principled BSDF material with the image as base color."""
    # Ensure the object has a material
    if not obj.data.materials:
        mat = bpy.data.materials.new(name=f"fal_{img.name}")
        obj.data.materials.append(mat)
    else:
        mat = obj.active_material
        if mat is None:
            mat = bpy.data.materials.new(name=f"fal_{img.name}")
            obj.data.materials.append(mat)

    mat.use_nodes = True
    tree = mat.node_tree

    # Find or create Principled BSDF
    principled = None
    for node in tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            principled = node
            break
    if principled is None:
        principled = tree.nodes.new("ShaderNodeBsdfPrincipled")

    # Find or create Image Texture node
    tex_node = None
    for node in tree.nodes:
        if node.type == "TEX_IMAGE":
            tex_node = node
            break
    if tex_node is None:
        tex_node = tree.nodes.new("ShaderNodeTexImage")
        tex_node.location = (principled.location.x - 300, principled.location.y)

    tex_node.image = img

    # Connect to Base Color
    base_color_input = principled.inputs.get("Base Color")
    if base_color_input:
        tree.links.new(tex_node.outputs["Color"], base_color_input)


def import_glb(
    filepath: str,
    *,
    name: str = "fal_model",
    location: tuple[float, float, float] | None = None,
) -> list[bpy.types.Object]:
    """Import a GLB file into the scene.

    Returns list of imported objects.
    """
    # Track objects before import
    before = set(bpy.data.objects)

    bpy.ops.import_scene.gltf(filepath=filepath)

    # Find newly imported objects
    after = set(bpy.data.objects)
    new_objects = list(after - before)

    # Rename root objects
    for i, obj in enumerate(new_objects):
        if obj.parent is None:  # root object
            suffix = f"_{i}" if i > 0 else ""
            obj.name = f"{name}{suffix}"

    # Optionally reposition
    if location is not None:
        for obj in new_objects:
            if obj.parent is None:
                obj.location = location

    return new_objects


def import_obj(
    filepath: str,
    *,
    name: str = "fal_model",
    location: tuple[float, float, float] | None = None,
) -> list[bpy.types.Object]:
    """Import an OBJ file into the scene.

    Returns list of imported objects.
    """
    before = set(bpy.data.objects)

    bpy.ops.wm.obj_import(filepath=filepath)

    after = set(bpy.data.objects)
    new_objects = list(after - before)

    for i, obj in enumerate(new_objects):
        if obj.parent is None:
            suffix = f"_{i}" if i > 0 else ""
            obj.name = f"{name}{suffix}"

    if location is not None:
        for obj in new_objects:
            if obj.parent is None:
                obj.location = location

    return new_objects


def resize_image_to_target(
    image_path: str,
    target_width: int,
    target_height: int,
) -> str:
    """Resize an image file to the target dimensions if they don't match.

    Overwrites the file in-place and returns the same path.
    Silently returns the original path if PIL is unavailable or on error.
    """
    try:
        from PIL import Image
    except ImportError:
        return image_path

    try:
        img = Image.open(image_path)
        if img.size == (target_width, target_height):
            return image_path

        print(
            f"fal.ai: Resizing result {img.size[0]}x{img.size[1]} "
            f"→ {target_width}x{target_height}"
        )
        img = img.resize((target_width, target_height), Image.LANCZOS)
        img.save(image_path)
    except Exception as e:
        print(f"fal.ai: Image resize failed, using original size: {e}")

    return image_path


def import_image_to_editor(
    image_path: str,
    *,
    name: str = "fal_result",
) -> bpy.types.Image:
    """Load an image and display it in an Image Editor (if one is open)."""
    img = bpy.data.images.load(image_path)
    img.name = name

    # Try to display in an open Image Editor
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = img
                break

    return img


def add_audio_to_vse(
    filepath: str,
    *,
    name: str = "fal_audio",
) -> Any:
    """Add an audio file as a sound strip in the VSE."""
    scene = bpy.context.scene

    if not scene.sequence_editor:
        scene.sequence_editor_create()

    se = scene.sequence_editor

    # Find first available channel
    channel = 1
    used_channels = {s.channel for s in se.sequences_all} if se.sequences_all else set()
    while channel in used_channels:
        channel += 1

    strip = se.sequences.new_sound(
        name=name,
        filepath=filepath,
        channel=channel,
        frame_start=scene.frame_current,
    )
    return strip


def add_video_to_vse(
    filepath: str,
    *,
    name: str = "fal_video",
) -> Any:
    """Add a video file as a movie + sound strip pair in the VSE.

    If the video contains an audio track, a sound strip is placed on
    the channel directly above the movie strip (mirroring Blender's
    native drag-and-drop behaviour).  Videos without audio produce
    only the movie strip.
    """
    scene = bpy.context.scene

    if not scene.sequence_editor:
        scene.sequence_editor_create()

    se = scene.sequence_editor

    used_channels = {s.channel for s in se.sequences_all} if se.sequences_all else set()
    channel = 1
    while channel in used_channels:
        channel += 1

    frame_start = scene.frame_current

    strip = se.sequences.new_movie(
        name=name,
        filepath=filepath,
        channel=channel,
        frame_start=frame_start,
    )

    sound_channel = channel + 1
    while sound_channel in used_channels:
        sound_channel += 1

    try:
        sound_strip = se.sequences.new_sound(
            name=f"{name}_audio",
            filepath=filepath,
            channel=sound_channel,
            frame_start=frame_start,
        )
        if sound_strip.frame_duration <= 1:
            se.sequences.remove(sound_strip)
            sound_strip = None
        elif sound_strip.frame_final_end != strip.frame_final_end:
            sound_strip.frame_final_end = strip.frame_final_end
    except Exception:
        sound_strip = None

    return strip
