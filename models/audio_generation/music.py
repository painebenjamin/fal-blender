from ..base import FalModel
from typing import Any

__all__ = [
    "MusicGenerationModel",
    "ElevenLabsMusicGenerationModel",
]

class MusicGenerationModel(FalModel):
    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["prompt"] = kwargs.get("prompt", None)
        return params

class ElevenLabsMusicGenerationModel(MusicGenerationModel):
    endpoint = "fal-ai/elevenlabs/music"