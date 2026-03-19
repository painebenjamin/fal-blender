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
        params["text"] = kwargs.get("text", None)
        return params

class ElevenLabsSoundEffectsGenerationModel(SpeechGenerationModel):
    endpoint = "fal-ai/elevenlabs/sound-effects/v2"