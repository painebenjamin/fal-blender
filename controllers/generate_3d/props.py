import bpy

from ...models import ImageTo3DModel, TextTo3DModel


class FalGenerate3DPropertyGroup(bpy.types.PropertyGroup):
    """Properties for text-to-3D and image-to-3D generation."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-3D", "Generate 3D model from text prompt"),
            ("IMAGE", "Image-to-3D", "Generate 3D model from an image"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=TextTo3DModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for text-to-3D",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=ImageTo3DModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for image-to-3D",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the 3D model you want to generate",
        default="",
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

    generate_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Generate materials for the 3D model",
        default=True,
    )
