import bpy

from ...models import ImageUpscalingModel, VideoUpscalingModel


class FalUpscalePropertyGroup(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("IMAGE", "Image", "Upscale an image"),
            ("VIDEO", "Video", "Upscale a video"),
        ],
        default="IMAGE",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=ImageUpscalingModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for image upscaling",
    )

    video_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=VideoUpscalingModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for video upscaling",
    )

    source: bpy.props.EnumProperty(
        name="Source",
        items=[
            ("FILE", "File", "Load from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
            ("TEXTURE", "Texture", "Use a texture from the blend file"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="File",
        description="Path to source image or video",
        subtype="FILE_PATH",
        default="",
    )

    texture_name: bpy.props.StringProperty(
        name="Texture",
        description="Name of the Blender image datablock to upscale",
        default="",
    )
