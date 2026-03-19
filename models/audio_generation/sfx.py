from ..base import FalModel
from typing import Any

__all__ = [
    "SoundEffectsGenerationModel",
    "ElevenLabsSoundEffectsGenerationModel",
]

class SoundEffectsGenerationModel(FalModel):
    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["text"] = kwargs.get("text", "")
        return params

class ElevenLabsSoundEffectsGenerationModel(SoundEffectsGenerationModel):
    endpoint = "fal-ai/elevenlabs/sound-effects/v2"
    display_name = "ElevenLabs Sound Effects v2"