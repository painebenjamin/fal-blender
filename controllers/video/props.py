import bpy

from ...models import ImageToVideoModel, TextToVideoModel
from ..advanced_params import with_advanced_params


@with_advanced_params
class FalVideoPropertyGroup(bpy.types.PropertyGroup):
    """Properties for text-to-video and image-to-video (VSE panel)."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-Video", "Generate video from text prompt"),
            ("IMAGE", "Image-to-Video", "Generate video from an image"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=TextToVideoModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for text-to-video",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=ImageToVideoModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for image-to-video",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the video you want to generate",
        default="",
    )

    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt for better results",
        default=True,
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
