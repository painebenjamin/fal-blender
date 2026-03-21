from ..base import AudioFalModel
from typing import Any, ClassVar

__all__ = [
    "SpeechGenerationModel",
    "ElevenLabsSpeechGenerationModel",
]

class SpeechGenerationModel(AudioFalModel):
    supports_preset: ClassVar[bool] = False
    supports_clone: ClassVar[bool] = False
    text_parameter = "text"

    @classmethod
    def enumerate(cls, **kwargs: Any) -> list[tuple[str, str, str]]:
        """
        Returns a list of all available models.
        """
        for_preset = kwargs.get("for_preset", False)
        for_clone = kwargs.get("for_clone", False)
        return [
            (subcls.__name__, subcls.display_name, subcls.description)
            for subcls in cls.__subclasses__()
            if subcls.is_available() and \
            ((for_preset and subcls.supports_preset) or not for_preset) and \
            ((for_clone and subcls.supports_clone) or not for_clone)
        ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["text"] = kwargs.get("text", None)
        return params


class ElevenLabsSpeechGenerationModel(SpeechGenerationModel):
    endpoint = "fal-ai/elevenlabs/tts/turbo-v2.5"
    display_name = "ElevenLabs TTS Turbo v2.5"
    supports_preset = True