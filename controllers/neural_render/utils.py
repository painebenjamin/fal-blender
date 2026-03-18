from __future__ import annotations

from ...utils import get_default_font

__all__ = [
    "get_dimensions",
    "overlay_labels",
    "is_occluded",
    "render_to_sketch",
]


def get_dimensions(context, props) -> tuple[int, int]:
    """Get render dimensions — from scene settings or manual override."""
    if props.use_scene_resolution:
        scene = context.scene
        scale = scene.render.resolution_percentage / 100.0
        return (
            int(scene.render.resolution_x * scale),
            int(scene.render.resolution_y * scale),
        )
    return (props.width, props.height)


def overlay_labels(context, image_path: str, width: int, height: int):
    """Overlay text labels on the rendered image using Pillow.

    Finds objects with 'fal_ai_label' custom property, projects their
    world position to 2D screen coordinates, and draws labels.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("fal.ai: Pillow not available, skipping label overlay")
        return

    scene = context.scene
    camera = scene.camera
    if not camera:
        return

    # Collect labeled objects
    props = scene.fal_neural_render
    labeled = []

    _skip_types = {"CAMERA", "LIGHT", "EMPTY", "ARMATURE"}
    _skip_names = {"Camera", "Light", "Sun", "Point", "Spot", "Area"}

    for obj in scene.objects:
        if obj.type in _skip_types:
            continue
        if not obj.visible_get():
            continue

        label = obj.get("fal_ai_label")
        if label and isinstance(label, str):
            labeled.append((obj, label))
        elif props.auto_label:
            name = obj.name
            if name in _skip_names:
                continue
            if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
                name = name[:-4]
            labeled.append((obj, name))

    if not labeled:
        return

    from mathutils import Vector  # type: ignore[import-not-found]

    depsgraph = context.evaluated_depsgraph_get()
    cam_obj = camera.evaluated_get(depsgraph)
    cam_data = cam_obj.data

    view_matrix = cam_obj.matrix_world.normalized().inverted()
    projection_matrix = cam_obj.calc_matrix_camera(depsgraph, x=width, y=height)

    def project_3d_to_2d(world_pos):
        co = (
            projection_matrix
            @ view_matrix
            @ Vector((world_pos[0], world_pos[1], world_pos[2], 1.0))
        )
        if co.w <= 0:
            return None
        ndc_x = co.x / co.w
        ndc_y = co.y / co.w
        px = int((ndc_x * 0.5 + 0.5) * width)
        py = int((1.0 - (ndc_y * 0.5 + 0.5)) * height)
        if 0 <= px < width and 0 <= py < height:
            return (px, py)
        return None

    def project_3d_to_2d_unclamped(world_pos):
        co = (
            projection_matrix
            @ view_matrix
            @ Vector((world_pos[0], world_pos[1], world_pos[2], 1.0))
        )
        if co.w <= 0:
            return None
        ndc_x = co.x / co.w
        ndc_y = co.y / co.w
        px = (ndc_x * 0.5 + 0.5) * width
        py = (1.0 - (ndc_y * 0.5 + 0.5)) * height
        return (px, py)

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    base_font_size = max(20, int(height * 0.03))
    font = get_default_font(base_font_size)
    padding = 6
    margin = int(height * 0.04)
    line_width = max(1, base_font_size // 12)

    depsgraph = context.evaluated_depsgraph_get()
    placed_labels = []

    for obj, label in labeled:
        anchor = None
        label_pos = None

        origin_occluded = camera and is_occluded(
            scene, depsgraph, camera, obj, width, height
        )
        if not origin_occluded:
            origin_2d = project_3d_to_2d(obj.matrix_world.translation)
            if origin_2d:
                anchor = origin_2d

        if anchor is None and hasattr(obj, "bound_box"):
            from mathutils import Vector  # type: ignore[import-not-found]

            for corner in obj.bound_box:
                world_pt = obj.matrix_world @ Vector(corner)
                if camera and is_occluded(
                    scene,
                    depsgraph,
                    camera,
                    obj,
                    width,
                    height,
                    override_pos=world_pt,
                ):
                    continue
                candidate = project_3d_to_2d(world_pt)
                if candidate is not None:
                    anchor = candidate
                    break

        if anchor is None:
            raw = project_3d_to_2d_unclamped(obj.matrix_world.translation)
            if raw is not None:
                proj_x, proj_y = int(raw[0]), int(raw[1])
                target_x = max(margin, min(proj_x, width - margin))
                target_y = max(margin, min(proj_y, height - margin))

                dist_left = target_x
                dist_right = width - target_x
                dist_top = target_y
                dist_bottom = height - target_y
                min_dist = min(dist_left, dist_right, dist_top, dist_bottom)

                if min_dist == dist_left:
                    anchor = (margin, target_y)
                elif min_dist == dist_right:
                    anchor = (width - margin, target_y)
                elif min_dist == dist_top:
                    anchor = (target_x, margin)
                else:
                    anchor = (target_x, height - margin)

        if anchor is None:
            continue

        ax, ay = anchor

        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        candidates = [
            (ax + margin, ay - margin - th),
            (ax + margin, ay + margin),
            (ax - margin - tw, ay - margin - th),
            (ax - margin - tw, ay + margin),
            (ax - tw // 2, ay - margin * 2 - th),
            (ax - tw // 2, ay + margin * 2),
        ]

        best = None
        for cx, cy in candidates:
            cx = max(padding, min(cx, width - tw - padding * 2))
            cy = max(padding, min(cy, height - th - padding * 2))
            rect = (cx - padding, cy - padding, cx + tw + padding, cy + th + padding)

            overlaps = False
            for pr in placed_labels:
                if (
                    rect[0] < pr[2]
                    and rect[2] > pr[0]
                    and rect[1] < pr[3]
                    and rect[3] > pr[1]
                ):
                    overlaps = True
                    break
            if not overlaps:
                best = (cx, cy, rect)
                break

        if best is None:
            cx, cy = candidates[0]
            cx = max(padding, min(cx, width - tw - padding * 2))
            cy = max(padding, min(cy, height - th - padding * 2))
            rect = (cx - padding, cy - padding, cx + tw + padding, cy + th + padding)
            best = (cx, cy, rect)

        lx, ly, label_rect = best
        placed_labels.append(label_rect)

        label_center_x = lx + tw // 2
        label_center_y = ly + th // 2
        dist = ((label_center_x - ax) ** 2 + (label_center_y - ay) ** 2) ** 0.5
        if dist > margin * 0.5:
            draw.line(
                [(ax, ay), (label_center_x, label_center_y)],
                fill=(0, 0, 0),
                width=line_width,
            )
            r = max(2, line_width + 1)
            draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(0, 0, 0))

        draw.rectangle(
            [label_rect[0], label_rect[1], label_rect[2], label_rect[3]],
            fill=(255, 255, 255),
            outline=(0, 0, 0),
            width=line_width,
        )
        draw.text((lx, ly), label, fill=(0, 0, 0), font=font)

    img.save(image_path)


# ---------------------------------------------------------------------------
# Occlusion testing for labels
# ---------------------------------------------------------------------------
def is_occluded(
    scene, depsgraph, camera, obj, width: int, height: int, override_pos=None
) -> bool:
    """Check if a point (default: object origin) is occluded from camera's view."""

    cam_loc = camera.matrix_world.translation
    obj_loc = override_pos if override_pos is not None else obj.matrix_world.translation

    direction = (obj_loc - cam_loc).normalized()
    distance = (obj_loc - cam_loc).length

    result, location, normal, index, hit_obj, matrix = scene.ray_cast(
        depsgraph, cam_loc + direction * 0.01, direction, distance=distance + 0.01
    )

    if not result:
        return False
    if hit_obj == obj:
        return False
    if hit_obj.parent == obj:
        return False

    hit_dist = (location - cam_loc).length
    obj_dist = distance
    if hit_dist < obj_dist - 0.1:
        return True

    return False


# ---------------------------------------------------------------------------
# Edge detection from render passes (PIL-based)
# ---------------------------------------------------------------------------
def render_to_sketch(render_path: str, width: int, height: int):
    """Convert a shaded render with freestyle lines into a clean sketch."""
    from PIL import Image, ImageChops, ImageFilter

    img = Image.open(render_path)
    gray = img.convert("L")

    edges = gray.filter(ImageFilter.FIND_EDGES)

    edges2 = gray.filter(
        ImageFilter.Kernel(
            size=(3, 3),
            kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
            scale=1,
            offset=0,
        )
    )

    edges_combined = ImageChops.lighter(edges, edges2)

    threshold = 12
    edge_lines = edges_combined.point(lambda p: 0 if p > threshold else 255)

    freestyle_mask = gray.point(lambda p: 0 if p < 40 else 255)

    combined = ImageChops.multiply(edge_lines, freestyle_mask)

    combined.convert("RGB").save(render_path)


# ---------------------------------------------------------------------------
# Scene depth analysis
# ---------------------------------------------------------------------------
def calc_scene_depth_bounds(scene, camera) -> tuple[float | None, float | None]:
    """Calculate the actual near/far depth of scene geometry from camera."""
    from mathutils import Vector  # type: ignore[import-not-found]

    cam_loc = camera.matrix_world.translation
    cam_forward = camera.matrix_world.to_3x3() @ Vector((0, 0, -1))
    cam_forward.normalize()

    min_dist = float("inf")
    max_dist = float("-inf")
    found = False

    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            continue
        if not obj.visible_get():
            continue

        bbox = obj.bound_box
        for corner in bbox:
            world_point = obj.matrix_world @ Vector(corner)
            to_point = world_point - cam_loc
            dist = to_point.dot(cam_forward)
            if dist > 0:
                min_dist = min(min_dist, dist)
                max_dist = max(max_dist, dist)
                found = True

    if not found:
        return (None, None)

    return (min_dist, max_dist)
