from typing import Any

from ..base import AudioFalModel

__all__ = [
    "MusicGenerationModel",
    "ElevenLabsMusicGenerationModel",
]


class MusicGenerationModel(AudioFalModel):
    """Base model for prompt-driven music generation."""

    prompt_parameter = "prompt"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["prompt"] = params.get("prompt", "")
        return params


class ElevenLabsMusicGenerationModel(MusicGenerationModel):
    """ElevenLabs music generation model."""

    endpoint = "fal-ai/elevenlabs/music"
    display_name = "ElevenLabs Music"
