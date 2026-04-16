import bpy

from ...models import DepthVideoModel, ImageToVideoModel, TextToVideoModel


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


class FalDepthVideoPropertyGroup(bpy.types.PropertyGroup):
    """Properties for depth-conditioned video generation (3D panel)."""

    depth_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=DepthVideoModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for depth video",
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

    use_scene_resolution: bpy.props.BoolProperty(
        name="Use Scene Resolution",
        description="Read dimensions from scene render settings",
        default=True,
    )

    width: bpy.props.IntProperty(
        name="W",
        description="Output width in pixels (only when 'Use Scene Resolution' is off)",
        default=1280,
        min=64,
        max=4096,
        step=16,
    )

    height: bpy.props.IntProperty(
        name="H",
        description="Output height in pixels (only when 'Use Scene Resolution' is off)",
        default=720,
        min=64,
        max=4096,
        step=16,
    )

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
