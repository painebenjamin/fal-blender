from ..base import AudioFalModel
from typing import Any

__all__ = [
    "SoundEffectsGenerationModel",
    "ElevenLabsSoundEffectsGenerationModel",
]

class SoundEffectsGenerationModel(AudioFalModel):
    pass

class ElevenLabsSoundEffectsGenerationModel(SoundEffectsGenerationModel):
    endpoint = "fal-ai/elevenlabs/sound-effects/v2"
    display_name = "ElevenLabs Sound Effects v2"
    prompt_parameter = "text"  # non-standard
    duration_parameter = "duration_seconds"  # non-standard