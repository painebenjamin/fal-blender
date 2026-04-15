from __future__ import annotations

import tempfile
from typing import Any, ClassVar

import bpy

from ...importers import import_image_to_editor, resize_image_to_target
from ...job_queue import FalJob, JobManager
from ...models import (DepthGuidedImageGenerationModel, ImageRefinementModel,
                       SketchGuidedImageGenerationModel)
from ...utils import (create_compositor_output_node, download_file,
                      ensure_compositor_enabled, get_compositor_node_tree,
                      get_eevee_engine, get_world_color, restore_compositor,
                      set_world_color, snapshot_compositor)
from ..operators import FalOperator
from .utils import (calc_scene_depth_bounds, get_dimensions, overlay_labels,
                    render_to_sketch)

SKETCH_GUIDED_IMAGE_GENERATION_MODELS = SketchGuidedImageGenerationModel.catalog()
DEPTH_GUIDED_IMAGE_GENERATION_MODELS = DepthGuidedImageGenerationModel.catalog()
IMAGE_REFINEMENT_MODELS = ImageRefinementModel.catalog()


class FalNeuralRenderOperator(FalOperator):
    """
    Operator for neural rendering.
    """

    label = "Neural Render"  # text in button in UI

    # Guard against overlapping renders
    _rendering: ClassVar[bool] = False

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Check if the operator is enabled.
        """
        if cls._rendering:
            return False
        if context.scene.camera is None:
            return False

        if props.mode == "SKETCH":
            return bool(props.sketch_system_prompt.strip() or props.prompt.strip())
        elif props.mode == "REFINE":
            return bool(props.refine_system_prompt.strip() or props.prompt.strip())

        return bool(props.prompt.strip())

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """
        Invoke the operator.
        """
        if not invoke:
            raise RuntimeError(
                "Neural render operator should be used as a modal operator"
            )

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
        self._render_w, self._render_h = get_dimensions(context, props)

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

        self._rendering = True

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
        wm.modal_handler_add(self._operator_instance)
        self.report({"INFO"}, "Rendering...")
        return {"RUNNING_MODAL"}

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator.
        """
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

    def _on_complete(self, *_args: Any) -> None:
        """
        Handler for render completion.
        """
        self._render_done = True

    def _on_cancel(self, *_args: Any) -> None:
        """
        Handler for render cancellation.
        """
        self._render_cancelled = True

    def _cleanup_modal(self, context: bpy.types.Context) -> None:
        """
        Clean up the modal state.
        """
        self._rendering = False
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

    def _setup_depth(self, context: bpy.types.Context) -> None:
        """
        Configure scene for depth map render via Mist pass + compositor.
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save current settings
        self._saved.update(
            {
                "engine": scene.render.engine,
                "film_transparent": scene.render.film_transparent,
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
                "use_compositing": scene.render.use_compositing,
                "use_pass_mist": view_layer.use_pass_mist,
            }
        )
        # Blender 4.x only: save use_nodes (deprecated in 5.x)
        if bpy.app.version < (5, 0, 0):
            self._saved["use_nodes"] = scene.use_nodes
        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        # Configure render
        scene.render.engine = get_eevee_engine()
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
            near, far = calc_scene_depth_bounds(scene, camera)
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
        tree = ensure_compositor_enabled(scene)
        self._saved_compositor = snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        rl_node = tree.nodes.new("CompositorNodeRLayers")
        rl_node.location = (0, 0)
        invert_node = tree.nodes.new("CompositorNodeInvert")
        invert_node.location = (300, 0)
        composite_node = create_compositor_output_node(tree)
        composite_node.location = (600, 0)
        tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
        tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

    def _finish_depth(self, context: bpy.types.Context) -> None:
        """
        Save depth render result, restore scene, upload and submit API job.
        """
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

    def _setup_sketch(self, context: bpy.types.Context) -> None:
        """
        Configure scene for Freestyle sketch render with emission materials.
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save render settings
        self._saved.update(
            {
                "engine": scene.render.engine,
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
                "film_transparent": scene.render.film_transparent,
                "use_freestyle": scene.render.use_freestyle,
                "vl_use_freestyle": view_layer.use_freestyle,
                "view_transform": scene.view_settings.view_transform,
                "look": scene.view_settings.look,
            }
        )
        if world:
            self._saved["world_color"] = get_world_color(world)

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
            obj
            for obj in scene.objects
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
        scene.render.engine = get_eevee_engine()
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
            set_world_color(world, (1.0, 1.0, 1.0))

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

    def _finish_sketch(self, context: bpy.types.Context) -> None:
        """
        Save sketch render, post-process, restore scene, add labels, submit.
        """
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
            render_to_sketch(tmp, self._render_w, self._render_h)
            print("fal.ai: Sketch post-processing complete")
        except Exception as e:
            print(f"fal.ai: Sketch post-processing failed, using raw render: {e}")

        # Restore scene state
        self._restore_state(context)

        # Overlay labels (after restore — uses camera projection + geometry)
        if self._enable_labels:
            overlay_labels(context, tmp, self._render_w, self._render_h, self._auto_label)

        # Upload and submit
        seed = self._seed if self._seed >= 0 else None
        args = self._model.parameters(
            prompt=self._prompt.strip(),
            system_prompt=self._sketch_system_prompt.strip(),
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

    def _setup_refine(self, context: bpy.types.Context) -> None:
        """
        Configure scene for a normal render (no scene modifications needed).
        """
        scene = context.scene

        # Save render settings so we can restore after
        self._saved.update(
            {
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
            }
        )

        # Set resolution
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100

    def _finish_refine(self, context: bpy.types.Context) -> None:
        """
        Save normal render, restore scene, upload and submit for img2img.
        """
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

        args = self._model.parameters(
            prompt=self._prompt.strip(),
            system_prompt=self._refine_system_prompt.strip(),
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
        self.report(
            {"INFO"},
            f"Render complete — refining (strength={self._refine_strength:.0%})...",
        )

    # ── Unified state restoration ──────────────────────────────────────

    def _restore_state(self, context: bpy.types.Context) -> None:
        """
        Restore all saved scene state (works for both depth and sketch).
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        s = self._saved

        # Restore compositor
        tree = get_compositor_node_tree(scene)
        if self._saved_compositor and tree:
            for node in tree.nodes:
                tree.nodes.remove(node)
            restore_compositor(tree, self._saved_compositor)
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
        # Blender 4.x only: restore use_nodes (deprecated in 5.x)
        if "use_nodes" in s and bpy.app.version < (5, 0, 0):
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
            set_world_color(world, s["world_color"])
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


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_neural_image_result(
    job: FalJob,
    render_w: int = 0,
    render_h: int = 0,
) -> None:
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
