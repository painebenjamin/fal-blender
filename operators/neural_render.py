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
from ..core.api import build_image_gen_args, download_file, upload_image_file
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
        description="Overlay text labels from objects with 'fal_ai_label' custom property",
        default=False,
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

            # Configure mist range from camera clip
            camera = scene.camera
            if camera and camera.data:
                cam_data = camera.data
                if world:
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
            endpoint=props.depth_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Depth: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Rendering depth + generating...")
        return {"FINISHED"}

    # ── Sketch Mode ────────────────────────────────────────────────────

    def _sketch_render(self, context, props) -> set[str]:
        """Render scene, optionally add labels, upload, reimagine."""
        scene = context.scene
        render_w, render_h = self._get_dimensions(context, props)

        old_res_x = scene.render.resolution_x
        old_res_y = scene.render.resolution_y

        try:
            scene.render.resolution_x = render_w
            scene.render.resolution_y = render_h
            bpy.ops.render.render()
        finally:
            scene.render.resolution_x = old_res_x
            scene.render.resolution_y = old_res_y

        render_img = bpy.data.images.get("Render Result")
        if not render_img:
            self.report({"ERROR"}, "Render failed — no result")
            return {"CANCELLED"}

        # Save render to temp
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        render_img.save_render(tmp.name)

        # Overlay labels if enabled
        if props.enable_labels:
            self._overlay_labels(context, tmp.name, render_w, render_h)

        # Upload
        image_url = upload_image_file(tmp.name)

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
            endpoint=props.sketch_endpoint,
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
        labeled = []
        for obj in scene.objects:
            label = obj.get("fal_ai_label")
            if label and isinstance(label, str):
                labeled.append((obj, label))

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

        # Draw labels
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img, "RGBA")

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (IOError, OSError):
            font = ImageFont.load_default()

        for obj, label in labeled:
            pos_2d = project_3d_to_2d(obj.matrix_world.translation)
            if pos_2d is None:
                continue

            px, py = pos_2d
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            padding = 4

            # Dark semi-transparent background
            draw.rectangle(
                [
                    px - padding,
                    py - padding,
                    px + tw + padding,
                    py + th + padding,
                ],
                fill=(0, 0, 0, 160),
            )
            # White text
            draw.text((px, py), label, fill=(255, 255, 255, 255), font=font)

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
