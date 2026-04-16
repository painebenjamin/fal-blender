from ...models import (DepthGuidedImageGenerationModel, ImageRefinementModel,
                       SketchGuidedImageGenerationModel)
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalNeuralRenderOperator
from .props import FalNeuralRenderPropertyGroup

# Models that support system prompts in refine mode
REFINE_MODELS = ImageRefinementModel.catalog()


def _show_refine_system_prompt(context, props) -> bool:
    """Show system prompt only for refine mode with models that support it."""
    if props.mode != "REFINE":
        return False
    model_cls = REFINE_MODELS.get(props.refine_endpoint)
    if model_cls is None:
        return False
    return getattr(model_cls, "supports_system_prompt", True)


class FalNeuralRenderController(FalController):
    """Controller for neural rendering workflows via fal.ai."""

    display_name = "Neural Render"
    description = "Render scene data and generates AI images via fal.ai"
    icon = "RENDER_RESULT"
    operator_class = FalNeuralRenderOperator
    properties_class = FalNeuralRenderPropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "mode",
            "depth_endpoint",
            "sketch_endpoint",
            "sketch_system_prompt",
            "enable_labels",
            "auto_label",
            "refine_endpoint",
            "refine_strength",
            "refine_system_prompt",
            "prompt",
            "enable_prompt_expansion",
            "use_scene_resolution",
            "width",
            "height",
            "seed",
        ],
        field_conditions={
            "enable_prompt_expansion": lambda context, props: props.mode != "SKETCH",
            "width": lambda context, props: not props.use_scene_resolution,
            "height": lambda context, props: not props.use_scene_resolution,
            "depth_endpoint": lambda context, props: props.mode == "DEPTH",
            "sketch_endpoint": lambda context, props: props.mode == "SKETCH",
            "sketch_system_prompt": lambda context, props: props.mode == "SKETCH",
            "enable_labels": lambda context, props: props.mode == "SKETCH",
            "auto_label": lambda context, props: props.mode == "SKETCH",
            "refine_endpoint": lambda context, props: props.mode == "REFINE",
            "refine_strength": lambda context, props: props.mode == "REFINE",
            "refine_system_prompt": _show_refine_system_prompt,
        },
        field_groupings=[
            {"width", "height"},
        ],
        endpoint_models={
            "depth_endpoint": DepthGuidedImageGenerationModel,
            "sketch_endpoint": SketchGuidedImageGenerationModel,
            "refine_endpoint": ImageRefinementModel,
        },
    )
