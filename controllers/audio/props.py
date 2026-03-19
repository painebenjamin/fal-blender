import bpy

from ...models import (
    SpeechGenerationModel,
    MusicGenerationModel,
    SoundEffectsGenerationModel,
)

class FalAudioPropertyGroup(bpy.types.PropertyGroup):
    # ── Common ──────────────────────────────────────────────────────────
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TTS", "Text-to-Speech", "Generate speech from text"),
            ("SFX", "Sound Effects", "Generate sound effects from prompt"),
            ("MUSIC", "Music", "Generate music from prompt"),
        ],
        default="TTS",
    )

    duration: bpy.props.FloatProperty(
        name="Duration",
        description="Duration in seconds",
        default=5.0,
        min=1.0,
        max=60.0,
    )

    # ── TTS Mode ──────────────────────────────────────────────────────────

    tts_preset_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SpeechGenerationModel.enumerate(for_preset=True) or [("NONE", "No Models Available", "")],
        description="Which model to use for TTS",
    )

    tts_clone_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SpeechGenerationModel.enumerate(for_clone=True) or [("NONE", "No Models Available", "")],
        description="Which model to use for TTS",
    )

    text: bpy.props.StringProperty(
        name="Text",
        description="Text to convert to speech",
        default="",
    )

    voice_mode: bpy.props.EnumProperty(
        name="Voice Mode",
        items=[
            ("PRESET", "Preset", "Use a voice preset"),
            ("CLONE", "Clone", "Clone voice from reference audio"),
        ],
        default="PRESET",
    )

    voice_preset: bpy.props.StringProperty(
        name="Voice Preset",
        description="Voice preset name/ID",
        default="",
    )

    voice_ref_path: bpy.props.StringProperty(
        name="Reference Audio",
        description="Path to reference audio for voice cloning",
        subtype="FILE_PATH",
        default="",
    )

    # ── SFX Mode ──────────────────────────────────────────────────────────

    sfx_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SoundEffectsGenerationModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for SFX",
    )

    sfx_prompt: bpy.props.StringProperty(
        name="SFX Prompt",
        description="Describe the sound effect",
        default="",
    )

    # ── Music Mode ──────────────────────────────────────────────────────────

    music_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=MusicGenerationModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for music",
    )

    music_prompt: bpy.props.StringProperty(
        name="Music Prompt",
        description="Describe the music (genre, mood, instruments)",
        default="",
    )
