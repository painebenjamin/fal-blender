from typing import Any, ClassVar

from ..base import AudioFalModel

__all__ = [
    "SpeechGenerationModel",
    "ElevenLabsSpeechGenerationModel",
    "MiniMaxSpeechGenerationModel",
]


class SpeechGenerationModel(AudioFalModel):
    """Base model for text-to-speech generation."""

    supports_preset: ClassVar[bool] = False
    supports_clone: ClassVar[bool] = False
    clone_endpoint: ClassVar[str | None] = None
    text_parameter = "text"
    voice_presets: ClassVar[list[str]] = []
    voice_parameter: ClassVar[str] = "voice"

    @classmethod
    def clone_parameters(
        cls, audio_url: str, text: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Build parameters for voice cloning. Override in subclasses with different APIs."""
        return {"audio_url": audio_url, "text": text}

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
    def get_voice_presets_for_model(cls, model_key: str) -> list[tuple[str, str, str]]:
        """Return Blender EnumProperty items for a specific model's voice presets.

        Looks up the model subclass by class name, reads its ``voice_presets``,
        and appends a *Custom* sentinel for free-form IDs.
        """
        catalog = cls.catalog()
        model = catalog.get(model_key)
        items: list[tuple[str, str, str]] = []
        if model and hasattr(model, "voice_presets"):
            for name in model.voice_presets:
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
        "Aria",
        "Roger",
        "Sarah",
        "Laura",
        "Charlie",
        "George",
        "Callum",
        "River",
        "Liam",
        "Charlotte",
        "Alice",
        "Matilda",
        "Will",
        "Jessica",
        "Eric",
        "Chris",
        "Brian",
        "Daniel",
        "Lily",
        "Bill",
    ]


class MiniMaxSpeechGenerationModel(SpeechGenerationModel):
    """MiniMax Speech Turbo text-to-speech model."""

    endpoint = "fal-ai/minimax/speech-2.8-turbo"
    clone_endpoint = "fal-ai/minimax/voice-clone"
    display_name = "MiniMax Speech Turbo"
    supports_preset = True
    supports_clone = True
    voice_presets = [
        "Wise_Woman",
        "Friendly_Person",
        "Inspirational_girl",
        "Deep_Voice_Man",
        "Calm_Woman",
        "Casual_Guy",
        "Lively_Girl",
        "Patient_Man",
        "Young_Knight",
        "Determined_Man",
        "Lovely_Girl",
        "Decent_Boy",
        "Imposing_Manner",
        "Elegant_Man",
        "Abbess",
        "Sweet_Girl_2",
        "Exuberant_Girl",
    ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """MiniMax uses 'prompt' (not 'text') and nested voice_setting.voice_id."""
        params: dict[str, Any] = {}
        text = kwargs.get("text", None)
        if text:
            params["prompt"] = text
        voice = kwargs.get("voice", None)
        if voice:
            params["voice_setting"] = {"voice_id": voice}
        params["output_format"] = "url"  # Get URL back, not hex
        return params
