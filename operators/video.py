# SPDX-License-Identifier: Apache-2.0
"""AI Video generation operators — text-to-video, image-to-video, depth video."""

from __future__ import annotations

import os
import tempfile

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TEXT_TO_VIDEO_ENDPOINTS,
    IMAGE_TO_VIDEO_ENDPOINTS,
    DEPTH_VIDEO_ENDPOINTS,
    endpoint_items,
)
from ..core.job_queue import FalJob, JobManager
from ..core.api import download_file, upload_image_file, upload_video_file


# ---------------------------------------------------------------------------
# Scene properties for video generation
# ---------------------------------------------------------------------------
class FalVideoProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-Video", "Generate video from text prompt"),
            ("IMAGE", "Image-to-Video", "Generate video from an image"),
            ("DEPTH", "Depth Video", "Depth-conditioned video generation"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(TEXT_TO_VIDEO_ENDPOINTS),
        description="Which model to use for text-to-video",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(IMAGE_TO_VIDEO_ENDPOINTS),
        description="Which model to use for image-to-video",
    )

    depth_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(DEPTH_VIDEO_ENDPOINTS),
        description="Which model to use for depth video",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the video you want to generate",
        default="",
    )

    use_scene_duration: bpy.props.BoolProperty(
        name="Use Scene Duration",
        description="Calculate duration from scene frame range and FPS",
        default=True,
    )

    duration: bpy.props.EnumProperty(
        name="Duration",
        items=[
            ("5", "5 seconds", ""),
            ("10", "10 seconds", ""),
        ],
        default="5",
    )

    use_scene_resolution: bpy.props.BoolProperty(
        name="Use Scene Resolution",
        description="Read dimensions from scene render settings",
        default=True,
    )

    image_source: bpy.props.EnumProperty(
        name="Image Source",
        items=[
            ("FILE", "File", "Load image from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="Image",
        description="Path to the source image",
        subtype="FILE_PATH",
        default="",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_scene_duration(scene) -> float:
    """Calculate scene duration in seconds from frame range and FPS."""
    fps = scene.render.fps / scene.render.fps_base
    frames = scene.frame_end - scene.frame_start + 1
    return frames / fps


def _get_scene_dimensions(scene) -> tuple[int, int]:
    """Get render dimensions applying resolution percentage."""
    scale = scene.render.resolution_percentage / 100.0
    return (
        int(scene.render.resolution_x * scale),
        int(scene.render.resolution_y * scale),
    )


def _calc_scene_depth_bounds(scene, camera) -> tuple[float | None, float | None]:
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
        for corner in obj.bound_box:
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


def _snapshot_compositor(tree) -> list[dict]:
    """Snapshot compositor node tree for restoration."""
    snapshot = []
    for node in tree.nodes:
        snapshot.append({
            "type": node.bl_idname,
            "name": node.name,
            "location": (node.location.x, node.location.y),
        })
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


def _render_depth_animation(context) -> str:
    """Render the scene's animation as a depth video (Mist pass).

    Returns path to the rendered MP4 file.
    Uses the same Mist + Invert compositor pipeline as neural render depth.
    """
    scene = context.scene
    view_layer = context.view_layer
    camera = scene.camera

    # Save ALL settings we'll touch
    old_engine = scene.render.engine
    old_film_transparent = scene.render.film_transparent
    old_use_compositing = scene.render.use_compositing
    old_use_nodes = scene.use_nodes
    old_use_pass_mist = view_layer.use_pass_mist
    old_view_transform = scene.view_settings.view_transform
    old_look = scene.view_settings.look
    old_file_format = scene.render.image_settings.file_format
    old_codec = getattr(scene.render.ffmpeg, "codec", "H264")
    old_format = getattr(scene.render.ffmpeg, "format", "MPEG4")
    old_output_path = scene.render.filepath
    old_color_mode = scene.render.image_settings.color_mode

    # Save world mist settings
    world = scene.world
    old_mist_start = 0.0
    old_mist_depth = 100.0
    if world:
        old_mist_start = world.mist_settings.start
        old_mist_depth = world.mist_settings.depth

    # Create temp output path
    tmp_dir = tempfile.mkdtemp(prefix="fal_depth_video_")
    output_path = os.path.join(tmp_dir, "depth")

    try:
        # Configure render
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.film_transparent = False
        scene.render.use_compositing = True

        # Standard color management (no Filmic dimming)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # Enable Mist pass
        view_layer.use_pass_mist = True

        # Configure mist range from actual scene depth
        if camera and world:
            near, far = _calc_scene_depth_bounds(scene, camera)
            if near is not None and far is not None:
                padding = (far - near) * 0.05
                world.mist_settings.start = max(0.0, near - padding)
                world.mist_settings.depth = (far - near) + padding * 2
                world.mist_settings.falloff = "LINEAR"
                print(f"fal.ai: Depth video range: {near:.2f} — {far:.2f}m")
            else:
                cam_data = camera.data
                world.mist_settings.start = cam_data.clip_start
                world.mist_settings.depth = cam_data.clip_end - cam_data.clip_start
                world.mist_settings.falloff = "LINEAR"

        # Build compositor: Mist → Invert → Composite (close=white, far=black)
        scene.use_nodes = True
        tree = scene.node_tree
        saved_nodes = _snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        rl_node = tree.nodes.new("CompositorNodeRLayers")
        rl_node.location = (0, 0)

        invert_node = tree.nodes.new("CompositorNodeInvert")
        invert_node.location = (300, 0)

        composite_node = tree.nodes.new("CompositorNodeComposite")
        composite_node.location = (600, 0)

        tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
        tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

        # Configure output as MP4 video
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.image_settings.color_mode = "BW"
        scene.render.filepath = output_path

        # Render the full animation
        print(f"fal.ai: Rendering depth video (frames {scene.frame_start}-{scene.frame_end})...")
        bpy.ops.render.render(animation=True)
        print("fal.ai: Depth video render complete")

        # Find the output file — Blender appends frame range to filename
        result_path = output_path + ".mp4"
        if not os.path.exists(result_path):
            # Try with frame numbers
            for f in os.listdir(tmp_dir):
                if f.endswith(".mp4"):
                    result_path = os.path.join(tmp_dir, f)
                    break

        if not os.path.exists(result_path):
            raise RuntimeError(f"Depth video not found at {result_path}")

        print(f"fal.ai: Depth video saved to {result_path}")
        return result_path

    finally:
        # Restore everything
        if scene.node_tree:
            for node in scene.node_tree.nodes:
                scene.node_tree.nodes.remove(node)
            _restore_compositor(scene.node_tree, saved_nodes)

        scene.use_nodes = old_use_nodes
        scene.render.engine = old_engine
        scene.render.film_transparent = old_film_transparent
        scene.render.use_compositing = old_use_compositing
        view_layer.use_pass_mist = old_use_pass_mist
        scene.view_settings.view_transform = old_view_transform
        scene.view_settings.look = old_look
        scene.render.image_settings.file_format = old_file_format
        scene.render.ffmpeg.format = old_format
        scene.render.ffmpeg.codec = old_codec
        scene.render.filepath = old_output_path
        scene.render.image_settings.color_mode = old_color_mode

        if world:
            world.mist_settings.start = old_mist_start
            world.mist_settings.depth = old_mist_depth


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_video(bpy.types.Operator):
    bl_idname = "fal.generate_video"
    bl_label = "Generate Video"
    bl_description = "Generate a video using fal.ai"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_video
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        elif props.mode == "IMAGE":
            return bool(
                props.image_path.strip() or props.image_source == "RENDER"
            )
        else:  # DEPTH
            return bool(props.prompt.strip()) and context.scene.camera is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_video

        if props.mode == "TEXT":
            return self._text_to_video(context, props)
        elif props.mode == "IMAGE":
            return self._image_to_video(context, props)
        else:
            return self._depth_video(context, props)

    def _get_duration(self, context, props) -> int:
        """Get video duration — from scene or manual override."""
        if props.use_scene_duration:
            return max(1, int(round(_get_scene_duration(context.scene))))
        return int(props.duration)

    def _get_num_frames(self, context, props) -> int:
        """Get number of frames for depth video from scene."""
        scene = context.scene
        fps = scene.render.fps / scene.render.fps_base
        duration = self._get_duration(context, props)
        # 16 fps is standard for wan-vace, but use scene fps if available
        return max(17, int(duration * min(fps, 16)))

    def _text_to_video(self, context, props) -> set[str]:
        duration = self._get_duration(context, props)
        args = {
            "prompt": props.prompt,
            "duration": duration,
        }

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.text_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Video: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Generating {duration}s video...")
        return {"FINISHED"}

    def _image_to_video(self, context, props) -> set[str]:
        if props.image_source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            image_url = upload_image_file(tmp.name)
        elif props.image_path:
            image_url = upload_image_file(bpy.path.abspath(props.image_path))
        else:
            self.report({"ERROR"}, "No image specified")
            return {"CANCELLED"}

        duration = self._get_duration(context, props)
        args = {
            "prompt": props.prompt,
            "image_url": image_url,
            "duration": duration,
        }

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.image_endpoint,
            arguments=args,
            on_complete=on_complete,
            label="Video from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Generating {duration}s video from image...")
        return {"FINISHED"}

    def _depth_video(self, context, props) -> set[str]:
        """Render depth animation, upload as video, submit to depth endpoint."""
        scene = context.scene

        if not scene.camera:
            self.report({"ERROR"}, "No camera in scene")
            return {"CANCELLED"}

        # Render the depth animation as MP4
        try:
            depth_video_path = _render_depth_animation(context)
        except Exception as e:
            self.report({"ERROR"}, f"Depth render failed: {e}")
            return {"CANCELLED"}

        # Upload the depth video
        video_url = upload_video_file(depth_video_path)

        # Build args for the depth video endpoint
        duration = self._get_duration(context, props)
        num_frames = self._get_num_frames(context, props)

        args = {
            "prompt": props.prompt,
            "video_url": video_url,
            "num_frames": num_frames,
        }

        # Merge endpoint default_params (e.g. ic_lora for LTX-2 depth)
        from ..endpoints import DEPTH_VIDEO_ENDPOINTS, get_endpoint
        ep = get_endpoint(DEPTH_VIDEO_ENDPOINTS, props.depth_endpoint)
        if ep and ep.default_params:
            for k, v in ep.default_params.items():
                args.setdefault(k, v)

        # Add resolution if using scene settings
        if props.use_scene_resolution:
            w, h = _get_scene_dimensions(scene)
            # Map to closest supported resolution
            if max(w, h) >= 1280:
                args["resolution"] = "720p"
            elif max(w, h) >= 580:
                args["resolution"] = "580p"
            else:
                args["resolution"] = "480p"

        def on_complete(job: FalJob):
            self._handle_video_result(job)

        job = FalJob(
            endpoint=props.depth_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Depth Video: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        scene_dur = _get_scene_duration(scene)
        self.report(
            {"INFO"},
            f"Rendering depth video ({scene_dur:.1f}s, {num_frames} frames)...",
        )
        return {"FINISHED"}

    def _handle_video_result(self, job: FalJob):
        """Download video result and import to VSE."""
        if job.status == "error":
            self.report({"ERROR"}, f"Video generation failed: {job.error}")
            return

        result = job.result or {}

        # Find video URL in result
        video_url = None
        for key in ["video", "output", "video_url"]:
            val = result.get(key)
            if isinstance(val, dict) and "url" in val:
                video_url = val["url"]
                break
            elif isinstance(val, str) and val.startswith("http"):
                video_url = val
                break

        if not video_url:
            self.report({"ERROR"}, "No video in response")
            return

        local_path = download_file(video_url, suffix=".mp4")

        # Import to VSE
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        se = scene.sequence_editor
        channel = 1
        used_channels = (
            {s.channel for s in se.sequences_all}
            if se.sequences_all
            else set()
        )
        while channel in used_channels:
            channel += 1

        se.sequences.new_movie(
            name="fal_video",
            filepath=local_path,
            channel=channel,
            frame_start=scene.frame_current,
        )
        self.report({"INFO"}, "Video imported to VSE!")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalVideoProperties,
    FAL_OT_generate_video,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_video = bpy.props.PointerProperty(
        type=FalVideoProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_video"):
        del bpy.types.Scene.fal_video
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
