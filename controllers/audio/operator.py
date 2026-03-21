from __future__ import annotations

import bpy

from ..base import FalOperator
from ...job_queue import FalJob, JobManager
from ...importers import add_audio_to_vse
from ...utils import download_file
from ...models import SpeechGenerationModel, MusicGenerationModel, SoundEffectsGenerationModel

SPEECH_GENERATION_MODELS = SpeechGenerationModel.catalog()
MUSIC_GENERATION_MODELS = MusicGenerationModel.catalog()
SOUND_EFFECTS_GENERATION_MODELS = SoundEffectsGenerationModel.catalog()

# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FalAudioOperator(FalOperator):
    """
    Audio operator.
    """
    label = "Generate Audio"  # text in button in UI

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Return True if the operator is enabled (i.e. if the button can be clicked)
        """
        if props.mode == "TTS":
            if props.voice_mode == "CLONE":
                if props.tts_clone_endpoint == "NONE" or not bool(props.voice_ref_path.strip()):
                    return False
            elif props.voice_mode == "PRESET":
                if props.tts_preset_endpoint == "NONE":
                    return False
            return bool(props.text.strip())
        elif props.mode == "SFX":
            if props.sfx_endpoint == "NONE":
                return False
            return bool(props.sfx_prompt.strip())
        else:  # MUSIC
            if props.music_endpoint == "NONE":
                return False
            return bool(props.music_prompt.strip())

    def _tts(self, context: bpy.types.Context, props: bpy.types.PropertyGroup) -> set[str]:
        """
        Generate text-to-speech audio.

        TODO: Implement voice cloning
        """
        if props.voice_mode == "PRESET":
            model = SPEECH_GENERATION_MODELS[props.tts_preset_endpoint]
        else:
            model = SPEECH_GENERATION_MODELS[props.tts_clone_endpoint]

        params = model.parameters(
            text=props.text,
            voice=props.voice_preset,
            duration=props.duration,
        )

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_tts")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"TTS: {props.text[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating speech...")
        return {"FINISHED"}

    def _sfx(self, context: bpy.types.Context, props: bpy.types.PropertyGroup) -> set[str]:
        """
        Generate sound effect audio.
        """
        model = SOUND_EFFECTS_GENERATION_MODELS[props.sfx_endpoint]
        params = model.parameters(
            prompt=props.sfx_prompt,
            duration=props.duration,
        )   

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_sfx")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"SFX: {props.sfx_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating sound effect...")
        return {"FINISHED"}

    def _music(self, context: bpy.types.Context, props: bpy.types.PropertyGroup) -> set[str]:
        """
        Generate music audio.
        """
        model = MUSIC_GENERATION_MODELS[props.music_endpoint]
        params = model.parameters(
            prompt=props.music_prompt,
            duration=props.duration,
        )

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_music")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Music: {props.music_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating music...")
        return {"FINISHED"}

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """
        Invoke the operator.
        """
        if props.mode == "TTS":
            return self._tts(context, props)
        elif props.mode == "SFX":
            return self._sfx(context, props)
        else:
            return self._music(context, props)


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_audio_result(job: FalJob, name: str):
    """Download audio result and add to VSE."""
    if job.status == "error":
        print(f"fal.ai: Audio generation failed: {job.error}")
        return

    result = job.result or {}
    audio_url = None
    for key in ["audio", "output", "audio_url", "audio_file"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            audio_url = val["url"]
            break
        elif isinstance(val, str) and val.startswith("http"):
            audio_url = val
            break

    if not audio_url:
        print("fal.ai: No audio in response")
        return

    local_path = download_file(audio_url, suffix=".wav")
    add_audio_to_vse(local_path, name=name)
    print("fal.ai: Audio added to VSE!")
