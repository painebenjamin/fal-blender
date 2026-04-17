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


def _vse_all_strips(se: bpy.types.SequenceEditor):
    """All VSE strips (incl. meta); Blender 5+ uses strips_all, 4.x uses sequences_all."""
    return se.strips_all if hasattr(se, "strips_all") else se.sequences_all


def _vse_editable_strips(se: bpy.types.SequenceEditor):
    """Collection with new_sound / new_movie / remove; Blender 5+ uses strips, 4.x uses sequences."""
    return se.strips if hasattr(se, "strips") else se.sequences


def _scene_render_resolution(scene: bpy.types.Scene) -> tuple[int, int]:
    """Return the scene's effective render resolution (including percentage scale)."""
    scale = scene.render.resolution_percentage / 100.0
    return (
        int(scene.render.resolution_x * scale),
        int(scene.render.resolution_y * scale),
    )


def _fit_movie_strip_to_target(
    scene: bpy.types.Scene,
    strip: Any,
    target_width: int | None,
    target_height: int | None,
) -> None:
    """Scale a movie strip so its native frame fits inside the target dimensions.

    Uniform scale preserves aspect ratio, so a clip whose aspect differs from
    the target is letterboxed (not cropped) — the user can tweak
    ``strip.transform.scale_*`` manually if they want cover-fit instead. If
    the caller passes ``None`` for both dimensions, no scaling is applied
    (leaves the strip at its native resolution).
    """
    if target_width is None and target_height is None:
        return
    if target_width is None or target_height is None:
        rx, ry = _scene_render_resolution(scene)
        if target_width is None:
            target_width = rx
        if target_height is None:
            target_height = ry

    if target_width <= 0 or target_height <= 0:
        return

    elements = getattr(strip, "elements", None)
    if not elements:
        return
    native_w = getattr(elements[0], "orig_width", 0)
    native_h = getattr(elements[0], "orig_height", 0)
    if native_w <= 0 or native_h <= 0:
        return

    transform = getattr(strip, "transform", None)
    if transform is None:
        return

    scale = min(target_width / native_w, target_height / native_h)
    transform.scale_x = scale
    transform.scale_y = scale


def _refresh_vse_for_scene(scene: bpy.types.Scene) -> None:
    """Force VSE areas showing this scene to pick up new strips.

    When we add strips from a timer callback, area UI state can stay stuck
    on the pre-callback snapshot (e.g. the VSE shows its "New" button even
    though ``sequence_editor`` now exists). ``tag_redraw`` + ``view_all``
    reconciles it. Best-effort: skipped if the WM isn't reachable.
    """
    try:
        wm = bpy.context.window_manager
    except AttributeError:
        return
    if wm is None:
        return

    for window in wm.windows:
        if window.scene is not scene:
            continue
        for area in window.screen.areas:
            if area.type != "SEQUENCE_EDITOR":
                continue
            area.tag_redraw()
            try:
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.sequencer.view_all()
            except Exception:
                pass


def add_audio_to_vse(
    filepath: str,
    *,
    name: str = "fal_audio",
    scene: bpy.types.Scene | None = None,
) -> Any:
    """Add an audio file as a sound strip in the VSE."""
    if scene is None:
        scene = bpy.context.scene

    if not scene.sequence_editor:
        scene.sequence_editor_create()

    se = scene.sequence_editor

    # Find first available channel
    channel = 1
    strips = _vse_editable_strips(se)
    used_channels = {s.channel for s in _vse_all_strips(se)}
    while channel in used_channels:
        channel += 1

    strip = strips.new_sound(
        name=name,
        filepath=filepath,
        channel=channel,
        frame_start=scene.frame_current,
    )
    _refresh_vse_for_scene(scene)
    return strip


def add_video_to_vse(
    filepath: str,
    *,
    name: str = "fal_video",
    target_width: int | None = None,
    target_height: int | None = None,
    scene: bpy.types.Scene | None = None,
) -> Any:
    """Add a video file as a movie + sound strip pair in the VSE.

    If the video contains an audio track, a sound strip is placed on
    the channel directly above the movie strip (mirroring Blender's
    native drag-and-drop behaviour).  Videos without audio produce
    only the movie strip.

    If ``target_width`` / ``target_height`` are provided (or defaulted from
    the scene render resolution), the movie strip's ``transform.scale`` is
    set so the clip fits that target while preserving aspect ratio — this
    is how we reconcile model output dimensions with the user's requested
    resolution without re-encoding.

    Pass ``scene`` explicitly from operator callbacks — ``bpy.context.scene``
    may have drifted by the time the job finishes (user switched scene or
    focus) and we want the strip to land where the render originated.
    """
    if scene is None:
        scene = bpy.context.scene

    if not scene.sequence_editor:
        scene.sequence_editor_create()

    se = scene.sequence_editor

    strips = _vse_editable_strips(se)
    used_channels = {s.channel for s in _vse_all_strips(se)}
    channel = 1
    while channel in used_channels:
        channel += 1

    frame_start = scene.frame_current

    strip = strips.new_movie(
        name=name,
        filepath=filepath,
        channel=channel,
        frame_start=frame_start,
    )

    _fit_movie_strip_to_target(scene, strip, target_width, target_height)

    sound_channel = channel + 1
    while sound_channel in used_channels:
        sound_channel += 1

    try:
        sound_strip = strips.new_sound(
            name=f"{name}_audio",
            filepath=filepath,
            channel=sound_channel,
            frame_start=frame_start,
        )
        if sound_strip.frame_duration <= 1:
            strips.remove(sound_strip)
            sound_strip = None
        elif sound_strip.frame_final_end != strip.frame_final_end:
            sound_strip.frame_final_end = strip.frame_final_end
    except Exception:
        sound_strip = None

    _refresh_vse_for_scene(scene)
    return strip
