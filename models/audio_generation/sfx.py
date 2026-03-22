from ..base import AudioFalModel

__all__ = [
    "SoundEffectsGenerationModel",
    "ElevenLabsSoundEffectsGenerationModel",
]


class SoundEffectsGenerationModel(AudioFalModel):
    """Base model for sound effects generation."""

    pass


class ElevenLabsSoundEffectsGenerationModel(SoundEffectsGenerationModel):
    """ElevenLabs Sound Effects v2 generation model."""

    endpoint = "fal-ai/elevenlabs/sound-effects/v2"
    display_name = "ElevenLabs Sound Effects v2"
    prompt_parameter = "text"  # non-standard
    duration_parameter = "duration_seconds"  # non-standard
