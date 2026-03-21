from ..base import AudioFalModel
from typing import Any

__all__ = [
    "MusicGenerationModel",
    "ElevenLabsMusicGenerationModel",
]

class MusicGenerationModel(AudioFalModel):
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
    endpoint = "fal-ai/elevenlabs/music"
    display_name = "ElevenLabs Music"