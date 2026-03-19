from __future__ import annotations

from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalAudioOperator
from .props import FalAudioPropertyGroup


audio_panel = FalControllerPanel(
    field_orders=[
        "mode",
        "duration",
        "tts_preset_endpoint",
        "tts_clone_endpoint",
        "sfx_endpoint",
        "music_endpoint",
        "text",
        "voice_mode",
        "voice_preset",
        "voice_ref_path",
        "sfx_prompt",
        "music_prompt",
    ],
    field_conditions={
        "tts_preset_endpoint": lambda context, props: props.mode == "TTS" and props.voice_mode == "PRESET",
        "tts_clone_endpoint": lambda context, props: props.mode == "TTS" and props.voice_mode == "CLONE",
        "sfx_endpoint": lambda context, props: props.mode == "SFX",
        "music_endpoint": lambda context, props: props.mode == "MUSIC",
        "voice_mode": lambda context, props: props.mode == "TTS",
        "voice_preset": lambda context, props: props.mode == "TTS" and props.voice_mode == "PRESET",
        "voice_ref_path": lambda context, props: props.mode == "TTS" and props.voice_mode == "CLONE",
        "sfx_prompt": lambda context, props: props.mode == "SFX",
        "music_prompt": lambda context, props: props.mode == "MUSIC",
    },
)

class FalAudioController(FalController):
    """
    Audio controller.
    """

    display_name = "Audio"
    description = "Generate audio using fal.ai"
    icon = "FILE_AUDIO"
    operator_class = FalAudioOperator
    properties_class = FalAudioPropertyGroup
    panel_3d = audio_panel
    panel_vse = audio_panel
