# SPDX-License-Identifier: Apache-2.0
"""AI Video generation operators — text-to-video, image-to-video, depth video.

Depth video uses modal operators with render handlers so Blender's UI stays
responsive during the internal depth animation render.
"""

from __future__ import annotations

import os
import tempfile

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TEXT_TO_VIDEO_ENDPOINTS,
    IMAGE_TO_VIDEO_ENDPOINTS,
    DEPTH_VIDEO_ENDPOINTS,
    endpoint_items,
    get_endpoint,
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

    # Depth mode: optional first-frame image
    depth_use_first_frame: bpy.props.BoolProperty(
        name="Use First Frame Image",
        description="Provide a reference image as the first frame for depth video",
        default=False,
    )

    depth_image_source: bpy.props.EnumProperty(
        name="First Frame Source",
        items=[
            ("FILE", "File", "Load image from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
            ("TEXTURE", "Blender Texture", "Use an existing Blender image"),
        ],
        default="RENDER",
    )

    depth_image_path: bpy.props.StringProperty(
        name="First Frame",
        description="Path to the first frame image",
        subtype="FILE_PATH",
        default="",
    )

    depth_texture_name: bpy.props.StringProperty(
        name="First Frame Texture",
        description="Blender image to use as first frame",
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


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_video(bpy.types.Operator):
    bl_idname = "fal.generate_video"
    bl_label = "Generate Video"
    bl_description = "Generate a video using fal.ai"
    bl_options = {"REGISTER"}

    # Guard against overlapping depth renders
    _rendering: bool = False

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_video
        if props.mode == "DEPTH" and cls._rendering:
            return False
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        elif props.mode == "IMAGE":
            return bool(
                props.image_path.strip() or props.image_source == "RENDER"
            )
        else:  # DEPTH
            return bool(props.prompt.strip()) and context.scene.camera is not None

    def invoke(self, context: bpy.types.Context, event) -> set[str]:
        props = context.scene.fal_video

        # TEXT and IMAGE modes are simple API calls — no rendering needed
        if props.mode == "TEXT":
            return self._text_to_video(context, props)
        elif props.mode == "IMAGE":
            return self._image_to_video(context, props)

        # DEPTH mode — render animation in modal
        return self._invoke_depth(context, props)

    def execute(self, context: bpy.types.Context) -> set[str]:
        # Fallback for non-invoke calls (shouldn't happen from UI)
        props = context.scene.fal_video
        if props.mode == "TEXT":
            return self._text_to_video(context, props)
        elif props.mode == "IMAGE":
            return self._image_to_video(context, props)
        else:
            self.report({"ERROR"}, "Depth video must be invoked from UI")
            return {"CANCELLED"}

    # ── DEPTH mode: modal entry point ──────────────────────────────────

    def _invoke_depth(self, context, props) -> set[str]:
        """Set up depth animation render and enter modal loop."""
        scene = context.scene

        if not scene.camera:
            self.report({"ERROR"}, "No camera in scene")
            return {"CANCELLED"}

        # Cache properties we'll need after render
        self._prompt = props.prompt
        self._endpoint = props.depth_endpoint
        self._use_scene_resolution = props.use_scene_resolution
        self._use_first_frame = props.depth_use_first_frame
        self._first_frame_source = props.depth_image_source
        self._first_frame_path = props.depth_image_path
        self._first_frame_texture = props.depth_texture_name

        # Calculate duration and frame count
        if props.use_scene_duration:
            self._duration = max(1, int(round(_get_scene_duration(scene))))
        else:
            self._duration = int(props.duration)

        fps = scene.render.fps / scene.render.fps_base
        self._num_frames = max(17, int(self._duration * min(fps, 16)))

        if self._use_scene_resolution:
            w, h = _get_scene_dimensions(scene)
            if max(w, h) >= 1280:
                self._resolution = "720p"
            elif max(w, h) >= 580:
                self._resolution = "580p"
            else:
                self._resolution = "480p"
        else:
            self._resolution = None

        # Modal state
        self._render_done = False
        self._render_cancelled = False
        self._timer = None
        self._saved = {}
        self._saved_compositor = []
        self._tmp_dir = None
        self._output_path = None

        # Pre-capture first-frame image BEFORE depth render overwrites
        # the Render Result with BW depth data
        self._first_frame_url = None
        if self._use_first_frame:
            self._first_frame_url = self._capture_first_frame()

        # Set up scene for depth animation render
        try:
            self._setup_depth_animation(context)
        except Exception as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Depth render setup failed: {e}")
            return {"CANCELLED"}

        FAL_OT_generate_video._rendering = True

        # Register render handlers
        self._handler_complete = self._on_complete
        self._handler_cancel = self._on_cancel
        bpy.app.handlers.render_complete.append(self._handler_complete)
        bpy.app.handlers.render_cancel.append(self._handler_cancel)

        # Start non-blocking animation render
        bpy.ops.render.render("INVOKE_DEFAULT", animation=True)

        # Enter modal loop
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)

        scene_dur = _get_scene_duration(scene)
        self.report(
            {"INFO"},
            f"Rendering depth animation ({scene_dur:.1f}s, {self._num_frames} frames)...",
        )
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if not (self._render_done or self._render_cancelled):
            return {"PASS_THROUGH"}

        # Render finished — clean up modal
        self._cleanup_modal(context)

        if self._render_cancelled:
            self._restore_state(context)
            self.report({"WARNING"}, "Depth render cancelled")
            return {"CANCELLED"}

        # Render succeeded — finalize
        self._finish_depth_animation(context)
        return {"FINISHED"}

    def _on_complete(self, *_args):
        self._render_done = True

    def _on_cancel(self, *_args):
        self._render_cancelled = True

    def _cleanup_modal(self, context):
        """Remove timer and render handlers."""
        FAL_OT_generate_video._rendering = False
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        for ref, handler_list in [
            (self._handler_complete, bpy.app.handlers.render_complete),
            (self._handler_cancel, bpy.app.handlers.render_cancel),
        ]:
            try:
                handler_list.remove(ref)
            except (ValueError, AttributeError):
                pass

    # ── DEPTH animation setup / finish ─────────────────────────────────

    def _setup_depth_animation(self, context):
        """Configure scene for depth video render (Mist pass, FFMPEG output)."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        camera = scene.camera

        # Save ALL settings we'll touch
        self._saved.update({
            "engine": scene.render.engine,
            "film_transparent": scene.render.film_transparent,
            "use_compositing": scene.render.use_compositing,
            "use_nodes": scene.use_nodes,
            "use_pass_mist": view_layer.use_pass_mist,
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "filepath": scene.render.filepath,
        })

        # FFMPEG settings (may not exist depending on Blender build)
        try:
            self._saved["ffmpeg_codec"] = scene.render.ffmpeg.codec
            self._saved["ffmpeg_format"] = scene.render.ffmpeg.format
        except AttributeError:
            pass

        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        # Create temp output path
        self._tmp_dir = tempfile.mkdtemp(prefix="fal_depth_video_")
        self._output_path = os.path.join(self._tmp_dir, "depth")

        # Configure render
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.film_transparent = False
        scene.render.use_compositing = True

        # Standard color management
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # Enable Mist pass
        view_layer.use_pass_mist = True

        # Configure mist range
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

        # Build compositor: Mist → Invert → Composite
        scene.use_nodes = True
        tree = scene.node_tree
        self._saved_compositor = _snapshot_compositor(tree)
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
        scene.render.filepath = self._output_path

    def _finish_depth_animation(self, context):
        """Find rendered video, restore scene, upload and submit API job."""
        # Find output file
        result_path = self._output_path + ".mp4"
        if not os.path.exists(result_path) and self._tmp_dir:
            for f in os.listdir(self._tmp_dir):
                if f.endswith(".mp4"):
                    result_path = os.path.join(self._tmp_dir, f)
                    break

        if not os.path.exists(result_path):
            self._restore_state(context)
            self.report({"ERROR"}, f"Depth video not found at {result_path}")
            return

        print(f"fal.ai: Depth video saved to {result_path}")

        # Restore scene state
        self._restore_state(context)

        # Upload and submit
        video_url = upload_video_file(result_path)

        args = {
            "prompt": self._prompt,
            "video_url": video_url,
            "num_frames": self._num_frames,
        }

        # Merge endpoint default_params (e.g. ic_lora for LTX-2 depth)
        ep = get_endpoint(DEPTH_VIDEO_ENDPOINTS, self._endpoint)
        if ep and ep.default_params:
            for k, v in ep.default_params.items():
                args.setdefault(k, v)

        # Optional first-frame image (pre-captured before depth render)
        if self._first_frame_url:
            args["image_url"] = self._first_frame_url

        # Resolution
        if self._resolution:
            args["resolution"] = self._resolution

        def on_complete(job: FalJob):
            FAL_OT_generate_video._handle_video_result(job)

        job = FalJob(
            endpoint=self._endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Depth Video: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Depth rendered — generating video...")

    def _restore_state(self, context):
        """Restore all saved scene state."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        s = self._saved

        # Restore compositor
        if self._saved_compositor and scene.node_tree:
            for node in scene.node_tree.nodes:
                scene.node_tree.nodes.remove(node)
            _restore_compositor(scene.node_tree, self._saved_compositor)
            self._saved_compositor = []

        # Restore render settings
        if "engine" in s:
            scene.render.engine = s["engine"]
        if "film_transparent" in s:
            scene.render.film_transparent = s["film_transparent"]
        if "use_compositing" in s:
            scene.render.use_compositing = s["use_compositing"]
        if "use_nodes" in s:
            scene.use_nodes = s["use_nodes"]
        if "use_pass_mist" in s:
            view_layer.use_pass_mist = s["use_pass_mist"]
        if "view_transform" in s:
            scene.view_settings.view_transform = s["view_transform"]
        if "look" in s:
            scene.view_settings.look = s["look"]
        if "file_format" in s:
            scene.render.image_settings.file_format = s["file_format"]
        if "color_mode" in s:
            scene.render.image_settings.color_mode = s["color_mode"]
        if "filepath" in s:
            scene.render.filepath = s["filepath"]

        try:
            if "ffmpeg_codec" in s:
                scene.render.ffmpeg.codec = s["ffmpeg_codec"]
            if "ffmpeg_format" in s:
                scene.render.ffmpeg.format = s["ffmpeg_format"]
        except AttributeError:
            pass

        if world:
            if "mist_start" in s:
                world.mist_settings.start = s["mist_start"]
            if "mist_depth" in s:
                world.mist_settings.depth = s["mist_depth"]

        self._saved.clear()

    def _capture_first_frame(self) -> str | None:
        """Capture the first-frame image NOW, before depth render overwrites state.

        Must be called before _setup_depth_animation because the depth render
        changes color_mode to BW and overwrites the Render Result.
        """
        try:
            if self._first_frame_source == "FILE":
                if not self._first_frame_path.strip():
                    return None
                return upload_image_file(self._first_frame_path)
            elif self._first_frame_source == "TEXTURE":
                img = bpy.data.images.get(self._first_frame_texture)
                if not img:
                    return None
                from ..core.api import upload_blender_image
                return upload_blender_image(img)
            else:  # RENDER
                render_img = bpy.data.images.get("Render Result")
                if not render_img:
                    print("fal.ai: No render result available for first frame")
                    return None
                # Save to disk immediately — Render Result will be overwritten
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="fal_first_frame_"
                )
                tmp.close()
                render_img.save_render(tmp.name)
                print(f"fal.ai: First frame captured to {tmp.name}")
                return upload_image_file(tmp.name)
        except Exception as e:
            print(f"fal.ai: Failed to capture first frame: {e}")
            return None

    def _get_depth_first_frame_url(self) -> str | None:
        """Upload the first-frame image for depth video and return its URL."""
        try:
            if self._first_frame_source == "FILE":
                if not self._first_frame_path.strip():
                    return None
                return upload_image_file(self._first_frame_path)
            elif self._first_frame_source == "TEXTURE":
                img = bpy.data.images.get(self._first_frame_texture)
                if not img:
                    return None
                from ..core.api import upload_blender_image
                return upload_blender_image(img)
            else:  # RENDER
                render_img = bpy.data.images.get("Render Result")
                if not render_img:
                    print("fal.ai: No render result available for first frame")
                    return None
                from ..core.api import upload_blender_image
                return upload_blender_image(render_img)
        except Exception as e:
            print(f"fal.ai: Failed to upload first frame: {e}")
            return None

    # ── TEXT and IMAGE modes (simple, non-modal) ───────────────────────

    def _get_duration(self, context, props) -> int:
        """Get video duration — from scene or manual override."""
        if props.use_scene_duration:
            return max(1, int(round(_get_scene_duration(context.scene))))
        return int(props.duration)

    def _text_to_video(self, context, props) -> set[str]:
        duration = self._get_duration(context, props)
        args = {
            "prompt": props.prompt,
            "duration": duration,
        }

        def on_complete(job: FalJob):
            FAL_OT_generate_video._handle_video_result(job)

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
            FAL_OT_generate_video._handle_video_result(job)

        job = FalJob(
            endpoint=props.image_endpoint,
            arguments=args,
            on_complete=on_complete,
            label="Video from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Generating {duration}s video from image...")
        return {"FINISHED"}

    # ── Result handling ────────────────────────────────────────────────

    @staticmethod
    def _handle_video_result(job: FalJob):
        """Download video result and import to VSE."""
        if job.status == "error":
            print(f"fal.ai: Video generation failed: {job.error}")
            return

        result = job.result or {}

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
            print("fal.ai: No video in response")
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
        print("fal.ai: Video imported to VSE!")


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
