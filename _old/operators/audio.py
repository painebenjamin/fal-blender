# SPDX-License-Identifier: Apache-2.0
"""Audio generation operators — TTS, SFX, Music."""

from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ..endpoints import (
    TTS_ENDPOINTS,
    SFX_ENDPOINTS,
    MUSIC_ENDPOINTS,
    endpoint_items,
)
from ..core.job_queue import FalJob, JobManager
from ..core.api import download_file, upload_image_file
from ..core.importers import add_audio_to_vse


# ---------------------------------------------------------------------------
# Scene properties for audio generation
# ---------------------------------------------------------------------------
class FalAudioProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TTS", "Text-to-Speech", "Generate speech from text"),
            ("SFX", "Sound Effects", "Generate sound effects from prompt"),
            ("MUSIC", "Music", "Generate music from prompt"),
        ],
        default="TTS",
    )

    tts_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(TTS_ENDPOINTS) or [("NONE", "No endpoints", "")],
        description="Which model to use for TTS",
    )

    sfx_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(SFX_ENDPOINTS) or [("NONE", "No endpoints", "")],
        description="Which model to use for SFX",
    )

    music_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=endpoint_items(MUSIC_ENDPOINTS) or [("NONE", "No endpoints", "")],
        description="Which model to use for music",
    )

    text: bpy.props.StringProperty(
        name="Text",
        description="Text to convert to speech",
        default="",
    )

    voice_mode: bpy.props.EnumProperty(
        name="Voice Mode",
        items=[
            ("PRESET", "Preset", "Use a voice preset"),
            ("CLONE", "Clone", "Clone voice from reference audio"),
        ],
        default="PRESET",
    )

    voice_preset: bpy.props.StringProperty(
        name="Voice Preset",
        description="Voice preset name/ID",
        default="",
    )

    voice_ref_path: bpy.props.StringProperty(
        name="Reference Audio",
        description="Path to reference audio for voice cloning",
        subtype="FILE_PATH",
        default="",
    )

    sfx_prompt: bpy.props.StringProperty(
        name="SFX Prompt",
        description="Describe the sound effect",
        default="",
    )

    music_prompt: bpy.props.StringProperty(
        name="Music Prompt",
        description="Describe the music (genre, mood, instruments)",
        default="",
    )

    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt for better results",
        default=True,
    )

    duration: bpy.props.FloatProperty(
        name="Duration",
        description="Duration in seconds",
        default=5.0,
        min=1.0,
        max=60.0,
    )


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


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FAL_OT_generate_audio(bpy.types.Operator):
    bl_idname = "fal.generate_audio"
    bl_label = "Generate Audio"
    bl_description = "Generate audio using fal.ai"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = context.scene.fal_audio
        if props.mode == "TTS":
            if props.tts_endpoint == "NONE":
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

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.fal_audio

        if props.mode == "TTS":
            return self._tts(context, props)
        elif props.mode == "SFX":
            return self._sfx(context, props)
        else:
            return self._music(context, props)

    def _tts(self, context, props) -> set[str]:
        args = {"text": props.text}

        if props.voice_mode == "CLONE" and props.voice_ref_path:
            ref_url = upload_image_file(
                bpy.path.abspath(props.voice_ref_path)
            )
            args["reference_audio"] = ref_url
        elif props.voice_preset:
            args["voice"] = props.voice_preset

        def on_complete(job: FalJob):
            _handle_audio_result(job, "fal_tts")

        job = FalJob(
            endpoint=props.tts_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"TTS: {props.text[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating speech...")
        return {"FINISHED"}

    def _sfx(self, context, props) -> set[str]:
        args = {
            "prompt": props.sfx_prompt,
            "expand_prompt": props.enable_prompt_expansion,
            "enable_prompt_expansion": props.enable_prompt_expansion,
            "duration": props.duration,
        }

        def on_complete(job: FalJob):
            _handle_audio_result(job, "fal_sfx")

        job = FalJob(
            endpoint=props.sfx_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"SFX: {props.sfx_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating sound effect...")
        return {"FINISHED"}

    def _music(self, context, props) -> set[str]:
        args = {
            "prompt": props.music_prompt,
            "expand_prompt": props.enable_prompt_expansion,
            "enable_prompt_expansion": props.enable_prompt_expansion,
            "duration": props.duration,
        }

        def on_complete(job: FalJob):
            _handle_audio_result(job, "fal_music")

        job = FalJob(
            endpoint=props.music_endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Music: {props.music_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating music...")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Helper to draw audio panel content
# ---------------------------------------------------------------------------
def _draw_audio_panel(layout, props):
    """Shared draw logic for audio panels."""
    layout.prop(props, "mode")

    if props.mode == "TTS":
        layout.prop(props, "tts_endpoint")
        layout.prop(props, "text")
        layout.prop(props, "voice_mode")
        if props.voice_mode == "PRESET":
            layout.prop(props, "voice_preset")
        else:
            layout.prop(props, "voice_ref_path")
    elif props.mode == "SFX":
        layout.prop(props, "sfx_endpoint")
        layout.prop(props, "sfx_prompt")
        layout.prop(props, "enable_prompt_expansion")
        layout.prop(props, "duration")
    else:  # MUSIC
        layout.prop(props, "music_endpoint")
        layout.prop(props, "music_prompt")
        layout.prop(props, "enable_prompt_expansion")
        layout.prop(props, "duration")

    row = layout.row()
    row.scale_y = 1.5
    row.operator("fal.generate_audio", icon="SOUND")


# ---------------------------------------------------------------------------
# VSE sidebar panel (duplicate for Sequence Editor)
# ---------------------------------------------------------------------------
class FAL_PT_audio_vse_panel(bpy.types.Panel):
    bl_label = "fal.ai Audio"
    bl_idname = "FAL_PT_audio_vse_panel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "fal.ai"

    def draw(self, context: bpy.types.Context) -> None:
        props = context.scene.fal_audio
        _draw_audio_panel(self.layout, props)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_classes = (
    FalAudioProperties,
    FAL_OT_generate_audio,
    FAL_PT_audio_vse_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_audio = bpy.props.PointerProperty(
        type=FalAudioProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "fal_audio"):
        del bpy.types.Scene.fal_audio
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
