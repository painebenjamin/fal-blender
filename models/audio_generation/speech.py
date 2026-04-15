from typing import Any, ClassVar

from ..base import AudioFalModel

__all__ = [
    "SpeechGenerationModel",
    "ElevenLabsSpeechGenerationModel",
]


class SpeechGenerationModel(AudioFalModel):
    """Base model for text-to-speech generation."""

    supports_preset: ClassVar[bool] = False
    supports_clone: ClassVar[bool] = False
    text_parameter = "text"
    voice_presets: ClassVar[list[str]] = []
    voice_parameter: ClassVar[str] = "voice"

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
            if subcls.is_available()
            and ((for_preset and subcls.supports_preset) or not for_preset)
            and ((for_clone and subcls.supports_clone) or not for_clone)
        ]

    @classmethod
    def enumerate_voice_presets(cls) -> list[tuple[str, str, str]]:
        """Return Blender EnumProperty items for voice presets.

        Each model subclass defines ``voice_presets``.  This helper merges
        all presets from all preset-capable subclasses, de-duplicates, and
        appends a *Custom* sentinel that lets the user type a free-form ID.
        """
        seen: set[str] = set()
        items: list[tuple[str, str, str]] = []
        for subcls in cls.__subclasses__():
            if not subcls.is_available() or not subcls.supports_preset:
                continue
            for name in subcls.voice_presets:
                if name in seen:
                    continue
                seen.add(name)
                items.append((name, name, f"Preset voice: {name}"))
        items.append(("__CUSTOM__", "Custom", "Enter a custom voice ID"))
        return items

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["text"] = kwargs.get("text", None)
        voice = kwargs.get("voice", None)
        if voice:
            params[cls.voice_parameter] = voice
        return params


class ElevenLabsSpeechGenerationModel(SpeechGenerationModel):
    """ElevenLabs TTS Turbo v2.5 speech generation model."""

    endpoint = "fal-ai/elevenlabs/tts/turbo-v2.5"
    display_name = "ElevenLabs TTS Turbo v2.5"
    supports_preset = True
    voice_presets = [
        "Aria", "Roger", "Sarah", "Laura", "Charlie", "George",
        "Callum", "River", "Liam", "Charlotte", "Alice", "Matilda",
        "Will", "Jessica", "Eric", "Chris", "Brian", "Daniel",
        "Lily", "Bill",
    ]
