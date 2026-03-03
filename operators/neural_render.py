# SPDX-License-Identifier: Apache-2.0
"""Neural Rendering operators — depth-controlled and sketch-based generation."""

from __future__ import annotations

import tempfile
import math

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    DEPTH_CONTROL_ENDPOINTS,
    IMAGE_GENERATION_ENDPOINTS,
    endpoint_items,
)
from ..core.api import build_image_gen_args, download_file, resolve_endpoint, upload_image_file
from ..core.job_queue import FalJob, JobManager


# ---------------------------------------------------------------------------
# Scene properties for neural rendering
# ---------------------------------------------------------------------------
class FalNeuralRenderProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("DEPTH", "Depth", "Render depth pass and generate image via depth ControlNet"),
            ("SKETCH", "Sketch", "Render scene and reimagine via image generation"),
        ],
        default="DEPTH",
    )

    depth_endpoint: bpy.props.EnumProperty(
        name="Depth Endpoint",
        items=endpoint_items(DEPTH_CONTROL_ENDPOINTS),
        description="Endpoint for depth-controlled generation",
    )

    sketch_endpoint: bpy.props.EnumProperty(
        name="Sketch Endpoint",
        items=endpoint_items(IMAGE_GENERATION_ENDPOINTS),
        description="Endpoint for sketch reimagining",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe what to generate from the rendered input",
        default="",
    )

    enable_labels: bpy.props.BoolProperty(
        name="Enable Labels",
        description="Overlay text labels on the sketch to guide generation",
        default=False,
    )

    auto_label: bpy.props.BoolProperty(
        name="Auto-label from Names",
        description="Use Blender object names as labels (no custom property needed). "
                    "Objects with 'fal_ai_label' custom property override their name",
        default=True,
    )

    use_scene_resolution: bpy.props.BoolProperty(
        name="Use Scene Resolution",
        description="Read dimensions from scene render settings (Output Properties)",
        default=True,
    )

    width: bpy.props.IntProperty(
        name="W",
        description="Output width in pixels (only when 'Use Scene Resolution' is off)",
        default=1024,
        min=64,
        max=4096,
        step=16,
    )

    height: bpy.props.IntProperty(
        name="H",
        description="Output height in pixels (only when 'Use Scene Resolution' is off)",
        default=1024,
        min=64,
        max=4096,
        step=16,
    )

    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed (-1 for random)",
        default=-1,
        min=-1,
        max=2147483647,
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_neural_render(bpy.types.Operator):
    bl_idname = "fal.neural_render"
    bl_label = "Neural Render"
    bl_description = "Render scene data and generate AI image via fal.ai"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_neural_render
        return bool(props.prompt.strip()) and context.scene.camera is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_neural_render

        if props.mode == "DEPTH":
            return self._depth_render(context, props)
        else:
            return self._sketch_render(context, props)

    @staticmethod
    def _get_dimensions(context, props) -> tuple[int, int]:
        """Get render dimensions — from scene settings or manual override."""
        if props.use_scene_resolution:
            scene = context.scene
            scale = scene.render.resolution_percentage / 100.0
            return (
                int(scene.render.resolution_x * scale),
                int(scene.render.resolution_y * scale),
            )
        return (props.width, props.height)

    # ── Depth Mode ─────────────────────────────────────────────────────

    def _depth_render(self, context, props) -> set[str]:
        """Render a proper depth map via compositor, upload, run depth ControlNet."""
        scene = context.scene
        render_w, render_h = self._get_dimensions(context, props)

        # ── Save ALL current settings we'll touch ──
        old_engine = scene.render.engine
        old_film_transparent = scene.render.film_transparent
        old_res_x = scene.render.resolution_x
        old_res_y = scene.render.resolution_y
        old_res_pct = scene.render.resolution_percentage
        old_use_compositing = scene.render.use_compositing
        old_use_nodes = scene.use_nodes

        view_layer = context.view_layer
        old_use_pass_mist = view_layer.use_pass_mist

        # Save world mist settings
        world = scene.world
        old_mist_start = 0.0
        old_mist_depth = 100.0
        if world:
            old_mist_start = world.mist_settings.start
            old_mist_depth = world.mist_settings.depth

        # Save existing compositor tree
        old_tree_links = []
        old_tree_nodes = []
        if scene.use_nodes and scene.node_tree:
            # We'll rebuild it after, so snapshot the state
            pass

        try:
            # ── Configure render ──
            scene.render.engine = "BLENDER_EEVEE_NEXT"
            scene.render.resolution_x = render_w
            scene.render.resolution_y = render_h
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = False
            scene.render.use_compositing = True

            # Enable Mist pass — gives 0-1 depth relative to camera
            view_layer.use_pass_mist = True

            # Configure mist range from actual scene depth bounds
            camera = scene.camera
            if camera and world:
                near, far = _calc_scene_depth_bounds(scene, camera)
                if near is not None and far is not None:
                    # Add small padding so objects at exact bounds aren't clipped
                    padding = (far - near) * 0.05
                    world.mist_settings.start = max(0.0, near - padding)
                    world.mist_settings.depth = (far - near) + padding * 2
                    world.mist_settings.falloff = "LINEAR"
                    print(f"fal.ai: Depth range: {near:.2f} — {far:.2f}m from camera")
                else:
                    # Fallback to camera clip range
                    cam_data = camera.data
                    world.mist_settings.start = cam_data.clip_start
                    world.mist_settings.depth = cam_data.clip_end - cam_data.clip_start
                    world.mist_settings.falloff = "LINEAR"

            # ── Build compositor for depth output ──
            # Mist pass → Invert (so close=white, far=black, MiDaS convention)
            # → Composite
            scene.use_nodes = True
            tree = scene.node_tree

            # Clear existing nodes
            _saved_nodes = _snapshot_compositor(tree)
            for node in tree.nodes:
                tree.nodes.remove(node)

            # Create depth pipeline
            rl_node = tree.nodes.new("CompositorNodeRLayers")
            rl_node.location = (0, 0)

            invert_node = tree.nodes.new("CompositorNodeInvert")
            invert_node.location = (300, 0)

            composite_node = tree.nodes.new("CompositorNodeComposite")
            composite_node.location = (600, 0)

            # Connect: Mist → Invert → Composite
            tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
            tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

            # ── Render ──
            bpy.ops.render.render()

            # Get result
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "Depth render failed — no result")
                return {"CANCELLED"}

            # Save depth map
            depth_path = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="fal_depth_"
            ).name
            render_img.save_render(depth_path)
            print(f"fal.ai: Depth map saved to {depth_path}")

        finally:
            # ── Restore everything ──
            # Restore compositor
            if scene.node_tree:
                for node in scene.node_tree.nodes:
                    scene.node_tree.nodes.remove(node)
                _restore_compositor(scene.node_tree, _saved_nodes)

            scene.use_nodes = old_use_nodes
            scene.view_settings.view_transform = old_view_transform
            scene.view_settings.look = old_look
            # Restore view settings
            scene.view_settings.view_transform = old_view_transform
            scene.view_settings.look = old_look

            # Restore world
            if scene.world and old_world_color is not None:
                _set_world_color(scene.world, old_world_color)

            # Restore materials
            for obj_name, mat_list in old_materials.items():
                obj = scene.objects.get(obj_name)
                if not obj:
                    continue
                for slot_idx, orig_mat in mat_list:
                    if slot_idx == -1:
                        if obj.data.materials:
                            obj.data.materials.pop()
                    elif slot_idx < len(obj.material_slots):
                        obj.material_slots[slot_idx].material = orig_mat
            for mat in sketch_mats:
                bpy.data.materials.remove(mat)

            # Restore lights
            for obj in hidden_lights:
                obj.hide_render = False

            scene.render.engine = old_engine
            scene.render.film_transparent = old_film_transparent
            scene.render.resolution_x = old_res_x
            scene.render.resolution_y = old_res_y
            scene.render.resolution_percentage = old_res_pct
            scene.render.use_compositing = old_use_compositing
            view_layer.use_pass_mist = old_use_pass_mist

            if world:
                world.mist_settings.start = old_mist_start
                world.mist_settings.depth = old_mist_depth

        # ── Upload and submit ──
        image_url = upload_image_file(depth_path)

        args = {
            "control_image_url": image_url,
            "image_url": image_url,
            "prompt": props.prompt,
        }
        seed = props.seed if props.seed >= 0 else None
        if seed is not None:
            args["seed"] = seed

        def on_complete(job: FalJob):
            self._handle_image_result(job)

        job = FalJob(
            endpoint=resolve_endpoint(props.depth_endpoint, args),
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Depth: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Rendering depth + generating...")
        return {"FINISHED"}

    # ── Sketch Mode ────────────────────────────────────────────────────

    def _sketch_render(self, context, props) -> set[str]:
        """Render scene as clean line art via Freestyle, optionally add labels, upload."""
        scene = context.scene
        render_w, render_h = self._get_dimensions(context, props)
        view_layer = context.view_layer

        # ── Save current settings ──
        old_engine = scene.render.engine
        old_res_x = scene.render.resolution_x
        old_res_y = scene.render.resolution_y
        old_res_pct = scene.render.resolution_percentage
        old_film_transparent = scene.render.film_transparent
        old_use_freestyle = view_layer.use_freestyle
        old_freestyle_use = scene.render.use_freestyle

        # No material override — render with default shading so edge detection
        # can find surface boundaries and intersections from shading contrast

        # Hide all lights to prevent shadow edges in sketch
        hidden_lights = []
        for obj in scene.objects:
            if obj.type == "LIGHT" and not obj.hide_render:
                obj.hide_render = True
                hidden_lights.append(obj)

        # Assign each object a unique gray emission so edge detection can
        # find boundaries between adjacent objects (same gray = no edge)
        sketch_mats = []  # track for cleanup
        old_materials = {}
        visible_meshes = [
            obj for obj in scene.objects
            if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}
            and obj.visible_get()
        ]

        # Spread gray values across 0.3–0.9 range, alternating to maximize
        # contrast between neighbors
        n = max(len(visible_meshes), 1)
        gray_values = []
        for i in range(n):
            # Interleave: even indices get light grays, odd get darker
            if i % 2 == 0:
                gray_values.append(0.9 - (i // 2) * (0.3 / max(n // 2, 1)))
            else:
                gray_values.append(0.4 + (i // 2) * (0.3 / max(n // 2, 1)))

        for idx, obj in enumerate(visible_meshes):
            old_materials[obj.name] = [
                (i, slot.material) for i, slot in enumerate(obj.material_slots)
            ]

            # Create unique emission material for this object
            g = max(0.3, min(0.95, gray_values[idx % len(gray_values)]))
            mat = bpy.data.materials.new(f"_fal_sketch_{idx}")
            mat.use_nodes = True
            mat_nodes = mat.node_tree.nodes
            mat_nodes.clear()
            emission = mat_nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (g, g, g, 1.0)
            emission.inputs["Strength"].default_value = 1.0
            mat_output = mat_nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(emission.outputs[0], mat_output.inputs[0])
            sketch_mats.append(mat)

            for slot in obj.material_slots:
                slot.material = mat
            if not obj.material_slots:
                obj.data.materials.append(mat)
                old_materials[obj.name].append((-1, None))

        try:
            # ── Configure for sketch rendering ──
            scene.render.engine = "BLENDER_EEVEE_NEXT"
            scene.render.resolution_x = render_w
            scene.render.resolution_y = render_h
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = False
            scene.render.use_freestyle = True
            view_layer.use_freestyle = True



            # Standard color management so emission renders as intended
            old_view_transform = scene.view_settings.view_transform
            old_look = scene.view_settings.look
            scene.view_settings.view_transform = "Standard"
            scene.view_settings.look = "None"

            # White world background
            old_world_color = None
            if scene.world:
                old_world_color = _get_world_color(scene.world)
                _set_world_color(scene.world, (1.0, 1.0, 1.0))

            # Configure freestyle for clean sketch lines
            freestyle = view_layer.freestyle_settings
            freestyle.crease_angle = 2.356  # ~135 degrees
            freestyle.as_render_pass = False  # Bake lines into the image

            # Ensure at least one lineset exists
            if not freestyle.linesets:
                ls = freestyle.linesets.new("Sketch Lines")
            else:
                ls = freestyle.linesets[0]

            ls.show_render = True
            ls.select_silhouette = True
            ls.select_border = True
            ls.select_crease = True
            ls.select_edge_mark = True
            ls.select_contour = True
            ls.select_external_contour = True
            ls.select_material_boundary = False
            ls.select_suggestive_contour = False

            # Line style: clean black lines, scale with resolution
            linestyle = ls.linestyle
            linestyle.color = (0.0, 0.0, 0.0)
            linestyle.thickness = max(2.0, render_w / 500.0)
            linestyle.alpha = 1.0

            # ── Render (Freestyle + emission white) ──
            bpy.ops.render.render()

            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "Sketch render failed — no result")
                return {"CANCELLED"}

            # Save freestyle render
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="fal_sketch_"
            ).name
            render_img.save_render(tmp)
            print(f"fal.ai: Freestyle sketch saved to {tmp}")

            # Post-process: convert shaded render to clean sketch
            # Edge detection catches intersections and surfaces Freestyle misses
            try:
                _render_to_sketch(tmp, render_w, render_h)
                print("fal.ai: Sketch post-processing complete")
            except Exception as e:
                print(f"fal.ai: Sketch post-processing failed, using raw render: {e}")

        finally:
            # Restore view settings
            scene.view_settings.view_transform = old_view_transform
            scene.view_settings.look = old_look

            # Restore world
            if scene.world and old_world_color is not None:
                _set_world_color(scene.world, old_world_color)

            # Restore materials
            for obj_name, mat_list in old_materials.items():
                obj = scene.objects.get(obj_name)
                if not obj:
                    continue
                for slot_idx, orig_mat in mat_list:
                    if slot_idx == -1:
                        if obj.data.materials:
                            obj.data.materials.pop()
                    elif slot_idx < len(obj.material_slots):
                        obj.material_slots[slot_idx].material = orig_mat
            for mat in sketch_mats:
                bpy.data.materials.remove(mat)

            # Restore lights
            for obj in hidden_lights:
                obj.hide_render = False

            scene.render.engine = old_engine
            scene.render.resolution_x = old_res_x
            scene.render.resolution_y = old_res_y
            scene.render.resolution_percentage = old_res_pct
            scene.render.film_transparent = old_film_transparent
            scene.render.use_freestyle = old_freestyle_use
            view_layer.use_freestyle = old_use_freestyle

        # Overlay labels if enabled
        if props.enable_labels:
            self._overlay_labels(context, tmp, render_w, render_h)

        # Upload
        image_url = upload_image_file(tmp)

        # Build args using the unified helper
        seed = props.seed if props.seed >= 0 else None
        # NBP uses image_urls (list), other endpoints use image_url (singular)
        # Send both for maximum compatibility
        args = build_image_gen_args(
            endpoint_id=props.sketch_endpoint,
            prompt=props.prompt,
            width=render_w,
            height=render_h,
            seed=seed,
            extra={
                "image_url": image_url,
                "image_urls": [image_url],
            },
        )

        def on_complete(job: FalJob):
            self._handle_image_result(job)

        job = FalJob(
            endpoint=resolve_endpoint(props.sketch_endpoint, args),
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Sketch: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Rendering sketch + generating...")
        return {"FINISHED"}

    @staticmethod
    def _overlay_labels(context, image_path: str, width: int, height: int):
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
        # Priority: fal_ai_label custom property > object name (if auto_label)
        props = scene.fal_neural_render
        labeled = []

        # Skip objects that are just scene infrastructure
        _skip_types = {"CAMERA", "LIGHT", "EMPTY", "ARMATURE"}
        _skip_names = {"Camera", "Light", "Sun", "Point", "Spot", "Area"}

        for obj in scene.objects:
            if obj.type in _skip_types:
                continue
            if not obj.visible_get():
                continue

            # Check for explicit label first
            label = obj.get("fal_ai_label")
            if label and isinstance(label, str):
                labeled.append((obj, label))
            elif props.auto_label:
                # Use object name, skip generic Blender defaults
                name = obj.name
                if name in _skip_names:
                    continue
                # Strip trailing .001, .002 etc.
                if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
                    name = name[:-4]
                labeled.append((obj, name))

        if not labeled:
            return

        # Camera matrices for projection
        from mathutils import Vector  # type: ignore[import-not-found]

        depsgraph = context.evaluated_depsgraph_get()
        cam_obj = camera.evaluated_get(depsgraph)
        cam_data = cam_obj.data

        # Model-view-projection
        view_matrix = cam_obj.matrix_world.normalized().inverted()
        if cam_data.type == "PERSP":
            projection_matrix = cam_obj.calc_matrix_camera(
                depsgraph, x=width, y=height
            )
        else:
            projection_matrix = cam_obj.calc_matrix_camera(
                depsgraph, x=width, y=height
            )

        def project_3d_to_2d(world_pos):
            """Project a 3D world position to 2D pixel coordinates."""
            co = projection_matrix @ view_matrix @ Vector(
                (world_pos[0], world_pos[1], world_pos[2], 1.0)
            )
            if co.w <= 0:
                return None  # Behind camera
            ndc_x = co.x / co.w
            ndc_y = co.y / co.w
            px = int((ndc_x * 0.5 + 0.5) * width)
            py = int((1.0 - (ndc_y * 0.5 + 0.5)) * height)
            if 0 <= px < width and 0 <= py < height:
                return (px, py)
            return None

        def project_3d_to_2d_unclamped(world_pos):
            """Project 3D to 2D without bounds check (for edge-clamped labels)."""
            co = projection_matrix @ view_matrix @ Vector(
                (world_pos[0], world_pos[1], world_pos[2], 1.0)
            )
            if co.w <= 0:
                return None
            ndc_x = co.x / co.w
            ndc_y = co.y / co.w
            px = (ndc_x * 0.5 + 0.5) * width
            py = (1.0 - (ndc_y * 0.5 + 0.5)) * height
            return (px, py)

        # Draw annotation-style labels: black text, white pill, leader lines
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Scale font size relative to image dimensions
        base_font_size = max(20, int(height * 0.03))
        font = _load_label_font(base_font_size)
        padding = 6
        margin = int(height * 0.04)  # Label offset from anchor point
        line_width = max(1, base_font_size // 12)

        depsgraph = context.evaluated_depsgraph_get()
        placed_labels = []  # Track placed label rects to avoid overlaps

        for obj, label in labeled:
            anchor = None  # Where the leader line points to
            label_pos = None  # Where the text goes

            # Try object origin first
            origin_occluded = camera and _is_occluded(
                scene, depsgraph, camera, obj, width, height
            )
            if not origin_occluded:
                origin_2d = project_3d_to_2d(obj.matrix_world.translation)
                if origin_2d:
                    anchor = origin_2d

            # If origin is occluded/off-screen, try bbox corners
            if anchor is None and hasattr(obj, "bound_box"):
                from mathutils import Vector  # type: ignore[import-not-found]
                for corner in obj.bound_box:
                    world_pt = obj.matrix_world @ Vector(corner)
                    if camera and _is_occluded(
                        scene, depsgraph, camera, obj, width, height,
                        override_pos=world_pt,
                    ):
                        continue
                    candidate = project_3d_to_2d(world_pt)
                    if candidate is not None:
                        anchor = candidate
                        break

            # If still no anchor, object is fully occluded — place label at
            # the image margin closest to the object's projected position,
            # with leader line pointing TOWARD where the object is
            if anchor is None:
                raw = project_3d_to_2d_unclamped(obj.matrix_world.translation)
                if raw is not None:
                    proj_x, proj_y = int(raw[0]), int(raw[1])

                    # Clamp the projected position to just inside the image
                    # This is where the leader line POINTS TO
                    target_x = max(margin, min(proj_x, width - margin))
                    target_y = max(margin, min(proj_y, height - margin))

                    # Place anchor at the nearest edge, offset from the target
                    # so the label sits at the margin and line points inward
                    dx = target_x - width / 2
                    dy = target_y - height / 2

                    # Choose the edge closest to the target
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

            # Calculate label text size
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Position label offset from anchor (prefer above-right)
            # Try multiple positions to avoid overlapping other labels
            candidates = [
                (ax + margin, ay - margin - th),     # above-right
                (ax + margin, ay + margin),           # below-right
                (ax - margin - tw, ay - margin - th), # above-left
                (ax - margin - tw, ay + margin),      # below-left
                (ax - tw // 2, ay - margin * 2 - th), # directly above
                (ax - tw // 2, ay + margin * 2),      # directly below
            ]

            best = None
            for cx, cy in candidates:
                # Clamp to image
                cx = max(padding, min(cx, width - tw - padding * 2))
                cy = max(padding, min(cy, height - th - padding * 2))
                rect = (cx - padding, cy - padding,
                        cx + tw + padding, cy + th + padding)

                # Check overlap with existing labels
                overlaps = False
                for pr in placed_labels:
                    if (rect[0] < pr[2] and rect[2] > pr[0] and
                            rect[1] < pr[3] and rect[3] > pr[1]):
                        overlaps = True
                        break
                if not overlaps:
                    best = (cx, cy, rect)
                    break

            if best is None:
                # All positions overlap — use first candidate anyway
                cx, cy = candidates[0]
                cx = max(padding, min(cx, width - tw - padding * 2))
                cy = max(padding, min(cy, height - th - padding * 2))
                rect = (cx - padding, cy - padding,
                        cx + tw + padding, cy + th + padding)
                best = (cx, cy, rect)

            lx, ly, label_rect = best
            placed_labels.append(label_rect)

            # Draw leader line from label to anchor
            label_center_x = lx + tw // 2
            label_center_y = ly + th // 2
            # Only draw line if label isn't right on top of anchor
            dist = ((label_center_x - ax) ** 2 + (label_center_y - ay) ** 2) ** 0.5
            if dist > margin * 0.5:
                draw.line(
                    [(ax, ay), (label_center_x, label_center_y)],
                    fill=(0, 0, 0), width=line_width,
                )
                # Small dot at anchor point
                r = max(2, line_width + 1)
                draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(0, 0, 0))

            # White background pill with thin black border
            draw.rectangle(
                [label_rect[0], label_rect[1], label_rect[2], label_rect[3]],
                fill=(255, 255, 255),
                outline=(0, 0, 0),
                width=line_width,
            )
            # Black text
            draw.text((lx, ly), label, fill=(0, 0, 0), font=font)

        img.save(image_path)

    # ── Result handling ────────────────────────────────────────────────

    def _handle_image_result(self, job: FalJob):
        """Download generated image and load into Blender."""
        if job.status == "error":
            self.report({"ERROR"}, f"Neural render failed: {job.error}")
            return

        result = job.result or {}
        image_url = None

        if "images" in result and result["images"]:
            image_url = result["images"][0].get("url")
        elif "image" in result:
            img = result["image"]
            image_url = img.get("url") if isinstance(img, dict) else img
        elif "output" in result:
            out = result["output"]
            if isinstance(out, dict) and "url" in out:
                image_url = out["url"]

        if not image_url:
            self.report({"ERROR"}, "No image in response")
            return

        local_path = download_file(image_url, suffix=".png")
        from ..core.importers import import_image_to_editor
        import_image_to_editor(local_path, name="fal_neural_render")
        self.report({"INFO"}, "Neural render complete!")


# ---------------------------------------------------------------------------
# World color helpers (handle node tree vs simple color)
# ---------------------------------------------------------------------------
def _get_world_color(world) -> tuple[float, float, float]:
    """Get current world background color, from nodes or fallback."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                c = node.inputs["Color"].default_value
                return (c[0], c[1], c[2])
    return tuple(world.color)


def _set_world_color(world, color: tuple[float, float, float]):
    """Set world background color, updating nodes if present."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                node.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
                return
    world.color = color


# ---------------------------------------------------------------------------
# Occlusion testing for labels
# ---------------------------------------------------------------------------
def _is_occluded(scene, depsgraph, camera, obj, width: int, height: int,
                 override_pos=None) -> bool:
    """Check if a point (default: object origin) is occluded from camera's view.

    Casts a ray from the camera toward the point. If it hits a different
    object first, the point is occluded.
    """
    from mathutils import Vector  # type: ignore[import-not-found]

    cam_loc = camera.matrix_world.translation
    obj_loc = override_pos if override_pos is not None else obj.matrix_world.translation

    direction = (obj_loc - cam_loc).normalized()
    distance = (obj_loc - cam_loc).length

    # Ray cast from camera toward object
    result, location, normal, index, hit_obj, matrix = scene.ray_cast(
        depsgraph, cam_loc + direction * 0.01, direction, distance=distance + 0.01
    )

    if not result:
        return False  # Nothing hit — object is visible (or not in ray path)

    # Hit something — is it the target object or one of its children?
    if hit_obj == obj:
        return False  # Hit the object itself — it's visible
    if hit_obj.parent == obj:
        return False  # Hit a child of the target

    # Something else is in the way — check distance
    hit_dist = (location - cam_loc).length
    obj_dist = distance
    if hit_dist < obj_dist - 0.1:
        return True  # Another object is closer → occluded

    return False


# ---------------------------------------------------------------------------
# Edge detection from render passes (PIL-based)
# ---------------------------------------------------------------------------
def _render_to_sketch(render_path: str, width: int, height: int):
    """Convert a shaded render with freestyle lines into a clean sketch.

    Process:
    1. Edge-detect the rendered image to find ALL edges (surfaces, intersections)
    2. Combine with the freestyle lines (which are already in the image)
    3. Output: black lines on white background
    """
    from PIL import Image, ImageFilter, ImageChops, ImageOps

    img = Image.open(render_path)
    gray = img.convert("L")

    # Edge detection on the full render — catches shading boundaries,
    # object intersections, surface changes, everything
    edges = gray.filter(ImageFilter.FIND_EDGES)

    # Also run a second pass with a different kernel for more detail
    edges2 = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
        scale=1,
        offset=0,
    ))

    # Combine both edge passes (take the stronger edge at each pixel)
    edges_combined = ImageChops.lighter(edges, edges2)

    # Threshold: strong edges become black lines
    threshold = 12
    edge_lines = edges_combined.point(lambda p: 0 if p > threshold else 255)

    # The freestyle lines in the original render are already black.
    # Extract them: anything significantly darker than the average
    # shading is a freestyle line
    freestyle_mask = gray.point(lambda p: 0 if p < 40 else 255)

    # Combine: multiply (black in either = black in result)
    combined = ImageChops.multiply(edge_lines, freestyle_mask)

    # Save as RGB
    combined.convert("RGB").save(render_path)


# ---------------------------------------------------------------------------
# Font loading for label overlay
# ---------------------------------------------------------------------------
def _load_label_font(size: int):
    """Load a readable font cross-platform. Falls back gracefully."""
    from PIL import ImageFont

    # Try common system font paths across platforms
    font_candidates = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]

    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue

    # Last resort: Pillow's built-in default (small but works everywhere)
    print("fal.ai: No system fonts found, using default (labels may be small)")
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Scene depth analysis
# ---------------------------------------------------------------------------
def _calc_scene_depth_bounds(scene, camera) -> tuple[float | None, float | None]:
    """Calculate the actual near/far depth of scene geometry from camera's perspective.

    Returns (near_distance, far_distance) in camera-space units,
    or (None, None) if no geometry found.
    """
    from mathutils import Vector  # type: ignore[import-not-found]

    cam_loc = camera.matrix_world.translation
    # Camera looks down its local -Z axis
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

        # Check all 8 corners of the object's bounding box
        bbox = obj.bound_box
        for corner in bbox:
            world_point = obj.matrix_world @ Vector(corner)
            # Project onto camera forward axis (signed distance)
            to_point = world_point - cam_loc
            dist = to_point.dot(cam_forward)
            if dist > 0:  # Only count things in front of camera
                min_dist = min(min_dist, dist)
                max_dist = max(max_dist, dist)
                found = True

    if not found:
        return (None, None)

    return (min_dist, max_dist)


# ---------------------------------------------------------------------------
# Compositor snapshot/restore helpers
# ---------------------------------------------------------------------------
def _snapshot_compositor(tree) -> list[dict]:
    """Snapshot compositor node tree for later restoration."""
    import json
    snapshot = []
    for node in tree.nodes:
        info = {
            "type": node.bl_idname,
            "name": node.name,
            "location": (node.location.x, node.location.y),
        }
        snapshot.append(info)
    # Snapshot links
    links = []
    for link in tree.links:
        links.append({
            "from_node": link.from_node.name,
            "from_socket": link.from_socket.name,
            "to_node": link.to_node.name,
            "to_socket": link.to_socket.name,
        })
    return [{"nodes": snapshot, "links": links}]


def _restore_compositor(tree, saved: list[dict]):
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalNeuralRenderProperties,
    FAL_OT_neural_render,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_neural_render = bpy.props.PointerProperty(
        type=FalNeuralRenderProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_neural_render"):
        del bpy.types.Scene.fal_neural_render
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
