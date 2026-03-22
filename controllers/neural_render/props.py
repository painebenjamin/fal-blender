import bpy

from ...models import (
    DepthGuidedImageGenerationModel,
    ImageRefinementModel,
    SketchGuidedImageGenerationModel,
)


class FalNeuralRenderPropertyGroup(bpy.types.PropertyGroup):
    # ── Common ──────────────────────────────────────────────────────────
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            (
                "DEPTH",
                "Depth",
                "Render depth pass and generate image via depth ControlNet",
            ),
            ("SKETCH", "Sketch", "Render scene and reimagine via image generation"),
            ("REFINE", "Refine", "Render normally then refine via image-to-image AI"),
        ],
        default="DEPTH",
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

    # ── Depth Mode ──────────────────────────────────────────────────────

    depth_endpoint: bpy.props.EnumProperty(
        name="Depth Endpoint",
        items=DepthGuidedImageGenerationModel.enumerate()
        or [("NONE", "No Models Available", "")],
        description="Endpoint for depth-controlled generation",
    )

    # ── Sketch Mode ──────────────────────────────────────────────────────

    sketch_endpoint: bpy.props.EnumProperty(
        name="Sketch Endpoint",
        items=SketchGuidedImageGenerationModel.enumerate()
        or [("NONE", "No Models Available", "")],
        description="Endpoint for sketch reimagining",
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

    # ── Refine Mode ──────────────────────────────────────────────────────

    refine_endpoint: bpy.props.EnumProperty(
        name="Refine Endpoint",
        items=ImageRefinementModel.enumerate() or [("NONE", "No Models Available", "")],
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
