# SPDX-License-Identifier: Apache-2.0
"""Neural Rendering operators — depth-controlled and sketch-based generation.

Uses modal operators with render handlers so Blender's UI stays responsive
during the internal render pass (depth map or Freestyle sketch).
"""

from __future__ import annotations

import tempfile
import math

import bpy  # type: ignore[import-not-found]

from ..models import (
    SketchGuidedImageGenerationModel,
    DepthGuidedImageGenerationModel,
    ImageRefinementModel,
)
from ..utils import download_file
from ..core.job_queue import FalJob, JobManager
from ..core.importers import import_image_to_editor, resize_image_to_target


SKETCH_GUIDED_IMAGE_GENERATION_MODELS = SketchGuidedImageGenerationModel.catalog()
DEPTH_GUIDED_IMAGE_GENERATION_MODELS = DepthGuidedImageGenerationModel.catalog()
IMAGE_REFINEMENT_MODELS = ImageRefinementModel.catalog()


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_neural_image_result(job: FalJob, render_w: int = 0, render_h: int = 0):
    """Download generated image and load into Blender."""
    if job.status == "error":
        print(f"fal.ai: Neural render failed: {job.error}")
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
        print("fal.ai: No image in response")
        return

    local_path = download_file(image_url, suffix=".png")
    if render_w > 0 and render_h > 0:
        resize_image_to_target(local_path, render_w, render_h)
    import_image_to_editor(local_path, name="fal_neural_render")
    print("fal.ai: Neural render complete!")


# ---------------------------------------------------------------------------
# Scene properties for neural rendering
# ---------------------------------------------------------------------------
class FalNeuralRenderProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("DEPTH", "Depth", "Render depth pass and generate image via depth ControlNet"),
            ("SKETCH", "Sketch", "Render scene and reimagine via image generation"),
            ("REFINE", "Refine", "Render normally then refine via image-to-image AI"),
        ],
        default="DEPTH",
    )

    depth_endpoint: bpy.props.EnumProperty(
        name="Depth Endpoint",
        items=DepthGuidedImageGenerationModel.enumerate(),
        description="Endpoint for depth-controlled generation",
    )

    sketch_endpoint: bpy.props.EnumProperty(
        name="Sketch Endpoint",
        items=SketchGuidedImageGenerationModel.enumerate(),
        description="Endpoint for sketch reimagining",
    )

    refine_endpoint: bpy.props.EnumProperty(
        name="Refine Endpoint",
        items=ImageRefinementModel.enumerate(),
        description="Endpoint for image-to-image refinement",
    )

    refine_strength: bpy.props.FloatProperty(
        name="Strength",
        description="How much AI changes the render (0 = no change, 1 = full reimagine)",
        default=0.35,
        min=0.0,
        max=1.0,
        step=5,
        precision=2,
    )

    sketch_system_prompt: bpy.props.StringProperty(
        name="System Prompt",
        description="Instructions for how the AI should interpret the sketch (Sketch mode only)",
        default=(
            "Render a photorealistic image that conforms to the layout presented. "
            "If labels are present on the image, follow those instructions to inform "
            "what should fill that space. Do not include the outlines or labels in "
            "your final image."
        ),
    )

    refine_system_prompt: bpy.props.StringProperty(
        name="System Prompt",
        description="Instructions for how the AI should refine the render (Refine mode only)",
        default=(
            "You are presented with a 3D-rendered image. Recreate this image in a "
            "photorealistic manner, being sure to represent the original artistic "
            "intent, only using a photorealistic style. Adjust lighting to be more "
            "realistic while adding details and texture where appropriate."
        ),
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe what to generate from the rendered input",
        default="",
    )

    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt for better results",
        default=True,
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

    # Guard against overlapping renders
    _rendering: bool = False

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if cls._rendering:
            return False
        if context.scene.camera is None:
            return False

        props = context.scene.fal_neural_render

        if props.mode == "SKETCH":
            return bool(props.sketch_system_prompt.strip() or props.prompt.strip())
        elif props.mode == "REFINE":
            return bool(props.refine_system_prompt.strip() or props.prompt.strip())

        return bool(props.prompt.strip())

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

    # ── Modal entry point ──────────────────────────────────────────────

    def invoke(self, context: bpy.types.Context, event) -> set[str]:
        props = context.scene.fal_neural_render

        # Cache everything we need — context may not be fully usable
        # from inside render handlers.
        self._mode = props.mode
        self._prompt = props.prompt
        self._seed = props.seed

        if self._mode == "DEPTH":
            self._model = DEPTH_GUIDED_IMAGE_GENERATION_MODELS[props.depth_endpoint]
        elif self._mode == "SKETCH":
            self._model = SKETCH_GUIDED_IMAGE_GENERATION_MODELS[props.sketch_endpoint]
        else:
            self._model = IMAGE_REFINEMENT_MODELS[props.refine_endpoint]

        self._refine_strength = props.refine_strength
        self._sketch_system_prompt = props.sketch_system_prompt
        self._refine_system_prompt = props.refine_system_prompt
        self._expand_prompt = props.enable_prompt_expansion
        self._enable_labels = props.enable_labels
        self._auto_label = props.auto_label
        self._render_w, self._render_h = self._get_dimensions(context, props)

        # Reset modal state
        self._render_done = False
        self._render_cancelled = False
        self._timer = None
        self._saved = {}
        self._sketch_mats = []
        self._old_materials = {}
        self._hidden_lights = []
        self._saved_compositor = []

        # Setup scene for the render
        try:
            if self._mode == "DEPTH":
                self._setup_depth(context)
            elif self._mode == "SKETCH":
                self._setup_sketch(context)
            else:
                self._setup_refine(context)
        except Exception as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Render setup failed: {e}")
            return {"CANCELLED"}

        FAL_OT_neural_render._rendering = True

        # Register render completion handlers — store refs for clean removal
        self._handler_complete = self._on_complete
        self._handler_cancel = self._on_cancel
        bpy.app.handlers.render_complete.append(self._handler_complete)
        bpy.app.handlers.render_cancel.append(self._handler_cancel)

        # Start non-blocking render (shows Blender's render progress bar)
        bpy.ops.render.render("INVOKE_DEFAULT")

        # Enter modal loop
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        self.report({"INFO"}, "Rendering...")
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if not (self._render_done or self._render_cancelled):
            return {"PASS_THROUGH"}

        # Render finished or was cancelled — clean up modal infrastructure
        self._cleanup_modal(context)

        if self._render_cancelled:
            self._restore_state(context)
            self.report({"WARNING"}, "Render cancelled")
            return {"CANCELLED"}

        # Render succeeded — save result, restore scene, upload & submit
        if self._mode == "DEPTH":
            self._finish_depth(context)
        elif self._mode == "SKETCH":
            self._finish_sketch(context)
        else:
            self._finish_refine(context)

        return {"FINISHED"}

    # ── Render handlers (called by Blender's render system) ────────────

    def _on_complete(self, *_args):
        self._render_done = True

    def _on_cancel(self, *_args):
        self._render_cancelled = True

    def _cleanup_modal(self, context):
        """Remove timer and render handlers."""
        FAL_OT_neural_render._rendering = False
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

    # ── Depth Mode — setup / finish ────────────────────────────────────

    def _setup_depth(self, context):
        """Configure scene for depth map render via Mist pass + compositor."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save current settings
        self._saved.update({
            "engine": scene.render.engine,
            "film_transparent": scene.render.film_transparent,
            "res_x": scene.render.resolution_x,
            "res_y": scene.render.resolution_y,
            "res_pct": scene.render.resolution_percentage,
            "use_compositing": scene.render.use_compositing,
            "use_nodes": scene.use_nodes,
            "use_pass_mist": view_layer.use_pass_mist,
        })
        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        # Configure render
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.use_compositing = True
        view_layer.use_pass_mist = True

        # Standard color management — Filmic compresses depth range
        self._saved["view_transform"] = scene.view_settings.view_transform
        self._saved["look"] = scene.view_settings.look
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # Mist range from actual scene depth bounds
        camera = scene.camera
        if camera and world:
            near, far = _calc_scene_depth_bounds(scene, camera)
            if near is not None and far is not None:
                # No padding — use the full 0-1 range for actual geometry
                # This gives maximum contrast in the depth map
                world.mist_settings.start = max(0.0, near)
                world.mist_settings.depth = max(0.01, far - near)
                world.mist_settings.falloff = "LINEAR"
                print(f"fal.ai: Depth range: {near:.2f} — {far:.2f}m from camera")
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

    def _finish_depth(self, context):
        """Save depth render result, restore scene, upload and submit API job."""
        render_img = bpy.data.images.get("Render Result")
        if not render_img:
            self._restore_state(context)
            self.report({"ERROR"}, "Depth render failed — no result")
            return

        depth_path = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_depth_"
        ).name
        render_img.save_render(depth_path)
        print(f"fal.ai: Depth map saved to {depth_path}")

        # Restore scene state before doing network I/O
        self._restore_state(context)

        args = self._model.parameters(
            image_path=depth_path,
            prompt=self._prompt,
            enable_prompt_expansion=self._expand_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=self._seed if self._seed >= 0 else None,
        )

        rw, rh = self._render_w, self._render_h
        def on_complete(job: FalJob):
            _handle_neural_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Depth: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Depth rendered — generating image...")

    # ── Sketch Mode — setup / finish ───────────────────────────────────

    def _setup_sketch(self, context):
        """Configure scene for Freestyle sketch render with emission materials."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save render settings
        self._saved.update({
            "engine": scene.render.engine,
            "res_x": scene.render.resolution_x,
            "res_y": scene.render.resolution_y,
            "res_pct": scene.render.resolution_percentage,
            "film_transparent": scene.render.film_transparent,
            "use_freestyle": scene.render.use_freestyle,
            "vl_use_freestyle": view_layer.use_freestyle,
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
        })
        if world:
            self._saved["world_color"] = _get_world_color(world)

        # Hide all lights
        self._hidden_lights = []
        for obj in scene.objects:
            if obj.type == "LIGHT" and not obj.hide_render:
                obj.hide_render = True
                self._hidden_lights.append(obj)

        # Assign each object a unique gray emission material
        self._sketch_mats = []
        self._old_materials = {}
        visible_meshes = [
            obj for obj in scene.objects
            if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}
            and obj.visible_get()
        ]

        n = max(len(visible_meshes), 1)
        gray_values = []
        for i in range(n):
            if i % 2 == 0:
                gray_values.append(0.9 - (i // 2) * (0.3 / max(n // 2, 1)))
            else:
                gray_values.append(0.4 + (i // 2) * (0.3 / max(n // 2, 1)))

        for idx, obj in enumerate(visible_meshes):
            self._old_materials[obj.name] = [
                (i, slot.material) for i, slot in enumerate(obj.material_slots)
            ]

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
            self._sketch_mats.append(mat)

            for slot in obj.material_slots:
                slot.material = mat
            if not obj.material_slots:
                obj.data.materials.append(mat)
                self._old_materials[obj.name].append((-1, None))

        # Configure render
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.use_freestyle = True
        view_layer.use_freestyle = True

        # Standard color management (no Filmic dimming)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # White world background
        if world:
            _set_world_color(world, (1.0, 1.0, 1.0))

        # Configure Freestyle
        freestyle = view_layer.freestyle_settings
        freestyle.crease_angle = 2.356  # ~135 degrees
        freestyle.as_render_pass = False

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

        linestyle = ls.linestyle
        linestyle.color = (0.0, 0.0, 0.0)
        linestyle.thickness = max(2.0, self._render_w / 500.0)
        linestyle.alpha = 1.0

    def _finish_sketch(self, context):
        """Save sketch render, post-process, restore scene, add labels, submit."""
        render_img = bpy.data.images.get("Render Result")
        if not render_img:
            self._restore_state(context)
            self.report({"ERROR"}, "Sketch render failed — no result")
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_sketch_"
        ).name
        render_img.save_render(tmp)
        print(f"fal.ai: Freestyle sketch saved to {tmp}")

        # Edge detection post-processing (before restore — just PIL work)
        try:
            _render_to_sketch(tmp, self._render_w, self._render_h)
            print("fal.ai: Sketch post-processing complete")
        except Exception as e:
            print(f"fal.ai: Sketch post-processing failed, using raw render: {e}")

        # Restore scene state
        self._restore_state(context)

        # Overlay labels (after restore — uses camera projection + geometry)
        if self._enable_labels:
            self._overlay_labels(context, tmp, self._render_w, self._render_h)

        # Upload and submit
        seed = self._seed if self._seed >= 0 else None

        # Compose full prompt: system prompt + user prompt
        system = self._sketch_system_prompt.strip()
        user = self._prompt.strip()
        if system and user:
            full_prompt = f'{system}\n\nFollow the user\'s prompt: "{user}"'
        elif system:
            full_prompt = system
        else:
            full_prompt = user

        args = self._model.parameters(
            prompt=full_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=seed,
            enable_prompt_expansion=self._expand_prompt,
            image_path=tmp,
        )

        rw, rh = self._render_w, self._render_h
        def on_complete(job: FalJob):
            _handle_neural_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Sketch: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Sketch rendered — generating image...")


    # ── Refine Mode — setup / finish ───────────────────────────────────

    def _setup_refine(self, context):
        """Configure scene for a normal render (no scene modifications needed)."""
        scene = context.scene

        # Save render settings so we can restore after
        self._saved.update({
            "res_x": scene.render.resolution_x,
            "res_y": scene.render.resolution_y,
            "res_pct": scene.render.resolution_percentage,
        })

        # Set resolution
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100

    def _finish_refine(self, context):
        """Save normal render, restore scene, upload and submit for img2img."""
        render_img = bpy.data.images.get("Render Result")
        if not render_img:
            self._restore_state(context)
            self.report({"ERROR"}, "Render failed — no result")
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_refine_"
        ).name
        render_img.save_render(tmp)
        print(f"fal.ai: Render saved for refinement: {tmp}")

        # Restore scene state
        self._restore_state(context)

        # Compose full prompt: system prompt + user prompt
        system = self._refine_system_prompt.strip()
        user = self._prompt.strip()
        if system and user:
            full_prompt = f'{system}\n\nFollow the user\'s prompt: "{user}"'
        elif system:
            full_prompt = system
        else:
            full_prompt = user

        args = self._model.parameters(
            prompt=full_prompt,
            image_path=tmp,
            strength=self._refine_strength,
            enable_prompt_expansion=self._expand_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=self._seed if self._seed >= 0 else None,
        )

        rw, rh = self._render_w, self._render_h
        def on_complete(job: FalJob):
            _handle_neural_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Neural Refine: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Render complete — refining (strength={self._refine_strength:.0%})...")

    # ── Unified state restoration ──────────────────────────────────────

    def _restore_state(self, context):
        """Restore all saved scene state (works for both depth and sketch)."""
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
        if "res_x" in s:
            scene.render.resolution_x = s["res_x"]
        if "res_y" in s:
            scene.render.resolution_y = s["res_y"]
        if "res_pct" in s:
            scene.render.resolution_percentage = s["res_pct"]
        if "use_compositing" in s:
            scene.render.use_compositing = s["use_compositing"]
        if "use_nodes" in s:
            scene.use_nodes = s["use_nodes"]
        if "use_pass_mist" in s:
            view_layer.use_pass_mist = s["use_pass_mist"]

        # Mist settings
        if world:
            if "mist_start" in s:
                world.mist_settings.start = s["mist_start"]
            if "mist_depth" in s:
                world.mist_settings.depth = s["mist_depth"]

        # Sketch-specific: view settings
        if "view_transform" in s:
            scene.view_settings.view_transform = s["view_transform"]
        if "look" in s:
            scene.view_settings.look = s["look"]
        if "world_color" in s and world:
            _set_world_color(world, s["world_color"])
        if "use_freestyle" in s:
            scene.render.use_freestyle = s["use_freestyle"]
        if "vl_use_freestyle" in s:
            view_layer.use_freestyle = s["vl_use_freestyle"]

        # Sketch-specific: restore materials
        for obj_name, mat_list in self._old_materials.items():
            obj = scene.objects.get(obj_name)
            if not obj:
                continue
            for slot_idx, orig_mat in mat_list:
                if slot_idx == -1:
                    if obj.data.materials:
                        obj.data.materials.pop()
                elif slot_idx < len(obj.material_slots):
                    obj.material_slots[slot_idx].material = orig_mat
        self._old_materials.clear()

        for mat in self._sketch_mats:
            bpy.data.materials.remove(mat)
        self._sketch_mats.clear()

        # Restore lights
        for obj in self._hidden_lights:
            obj.hide_render = False
        self._hidden_lights.clear()

        self._saved.clear()

    # ── Label overlay (unchanged) ──────────────────────────────────────

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
        projection_matrix = cam_obj.calc_matrix_camera(
            depsgraph, x=width, y=height
        )

        def project_3d_to_2d(world_pos):
            co = projection_matrix @ view_matrix @ Vector(
                (world_pos[0], world_pos[1], world_pos[2], 1.0)
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

        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        base_font_size = max(20, int(height * 0.03))
        font = _load_label_font(base_font_size)
        padding = 6
        margin = int(height * 0.04)
        line_width = max(1, base_font_size // 12)

        depsgraph = context.evaluated_depsgraph_get()
        placed_labels = []

        for obj, label in labeled:
            anchor = None
            label_pos = None

            origin_occluded = camera and _is_occluded(
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
                    if camera and _is_occluded(
                        scene, depsgraph, camera, obj, width, height,
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
                rect = (cx - padding, cy - padding,
                        cx + tw + padding, cy + th + padding)

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
                cx, cy = candidates[0]
                cx = max(padding, min(cx, width - tw - padding * 2))
                cy = max(padding, min(cy, height - th - padding * 2))
                rect = (cx - padding, cy - padding,
                        cx + tw + padding, cy + th + padding)
                best = (cx, cy, rect)

            lx, ly, label_rect = best
            placed_labels.append(label_rect)

            label_center_x = lx + tw // 2
            label_center_y = ly + th // 2
            dist = ((label_center_x - ax) ** 2 + (label_center_y - ay) ** 2) ** 0.5
            if dist > margin * 0.5:
                draw.line(
                    [(ax, ay), (label_center_x, label_center_y)],
                    fill=(0, 0, 0), width=line_width,
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

    # ── Result handling ────────────────────────────────────────────────


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
    """Check if a point (default: object origin) is occluded from camera's view."""
    from mathutils import Vector  # type: ignore[import-not-found]

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
def _render_to_sketch(render_path: str, width: int, height: int):
    """Convert a shaded render with freestyle lines into a clean sketch."""
    from PIL import Image, ImageFilter, ImageChops, ImageOps

    img = Image.open(render_path)
    gray = img.convert("L")

    edges = gray.filter(ImageFilter.FIND_EDGES)

    edges2 = gray.filter(ImageFilter.Kernel(
        size=(3, 3),
        kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
        scale=1,
        offset=0,
    ))

    edges_combined = ImageChops.lighter(edges, edges2)

    threshold = 12
    edge_lines = edges_combined.point(lambda p: 0 if p > threshold else 255)

    freestyle_mask = gray.point(lambda p: 0 if p < 40 else 255)

    combined = ImageChops.multiply(edge_lines, freestyle_mask)

    combined.convert("RGB").save(render_path)


# ---------------------------------------------------------------------------
# Font loading for label overlay
# ---------------------------------------------------------------------------
def _load_label_font(size: int):
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
# Scene depth analysis
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Compositor snapshot/restore helpers
# ---------------------------------------------------------------------------
def _snapshot_compositor(tree) -> list[dict]:
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
