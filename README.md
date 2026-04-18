# fal.ai Blender Extension

AI-powered 3D, materials, rendering, video, and audio — directly inside Blender.

**Work in progress and not officially supported. If/when this is officially supported, the repository will be moved under fal's GitHub organization.**

---

## Quick Start

1. Install the addon (see [Installation](#installation))
2. Enable **fal.ai — AI Generation Suite** in `Edit → Preferences → Add-ons`
3. Set your [fal.ai](https://fal.ai) API key in the addon preferences
4. Open the sidebar (`N`) in either the **3D Viewport** or the **Video Sequence Editor** and click the **fal.ai** tab
5. Pick a workflow, configure its parameters, and click **Generate**

Jobs run in the background — keep working and they'll appear in the **Active Jobs** sub-panel. Multiple jobs can run at once.

---

## 3D Panel Workflows

Available in the 3D Viewport sidebar under the **fal.ai** tab.

### 3D Generation

One controller, two modes. Imports the resulting mesh at the 3D cursor as GLB (falls back to OBJ + MTL + texture when needed).

#### Text-to-3D

<!-- video: text-to-3d -->

Generate a textured 3D mesh from a prompt. Exposes endpoint-specific controls (face budget, symmetry, pose hints, art style, quad vs triangle topology, etc.) conditionally based on which endpoint you pick.

| Endpoint | Notes |
|----------|-------|
| Meshy v6 Preview | Fast geometry + texture, 100–300k face budget, pose / symmetry hints |
| Hunyuan 3D v3.1 Pro | High-fidelity, 40k–1.5M faces, optional geometry-only output |
| Hunyuan 3D v3.1 Rapid | Quick turnaround, geometry-only toggle |
| Tripo P1 | Low-poly friendly, 48–20k face budget |
| Tripo H3.1 | Quad topology option, real-world auto-sizing, separate texture-seed |

#### Image-to-3D

<!-- video: image-to-3d -->

Same endpoints, but conditioned on a source image (file on disk or current render result). Prompt is still available as an optional guide.

| Endpoint | Notes |
|----------|-------|
| Meshy v6 Preview | Pose / symmetry hints, texture prompt |
| Hunyuan 3D v3.1 Pro | Geometry-only option |
| Hunyuan 3D v3.1 Rapid | Geometry-only option |
| Tripo P1 | Low-poly |
| Tripo H3.1 | Orientation + texture-alignment controls for image-to-3D |

---

### Materials

One controller, three modes. Produces a full Principled BSDF material (base color, roughness, metalness, normal, displacement) applied to the selected object.

#### Text-to-Material

<!-- video: text-to-material -->

Generate a complete tiling PBR material from a text prompt. Runs the full Patina pipeline.

| Endpoint | Notes |
|----------|-------|
| Patina | Generates base color + all PBR maps from a prompt |

#### Image-to-Maps

<!-- video: image-to-maps -->

Estimate PBR maps (roughness, normal, displacement, metalness) from an existing base-color image. Useful when you already have a texture and want the rest of the stack.

| Endpoint | Notes |
|----------|-------|
| Patina (PBR from Image) | Estimates PBR maps from a supplied base-color image |

There's also a **Tiling Texture** sub-mode if you just want a seamless base color from a prompt without the PBR stack.

---

### Image Rendering (Neural Render)

One controller, four image modes. Each mode does a quick technical render of the scene (depth, edges, sketch, or a normal render), then hands that off to fal as conditioning for an AI image.

#### Depth-to-Image

<!-- video: depth-to-image -->

Renders a Mist depth pass, then generates an AI image guided by scene depth. Great for preserving spatial layout while restyling.

| Endpoint | Notes |
|----------|-------|
| Z-Image Turbo (ControlNet) | Fast, general-purpose |
| FLUX.1 [dev] (ControlNet) | Higher quality, slower |

#### Edge-to-Image

<!-- video: edge-to-image -->

Runs Canny edge detection on a scene render and uses the edges as structural guidance for the AI image.

| Endpoint | Notes |
|----------|-------|
| Z-Image Turbo (ControlNet) | Fast |
| FLUX.1 [dev] (ControlNet) | Higher quality |

#### Sketch-to-Image

<!-- video: sketch-to-image -->

Renders a Freestyle line drawing (optionally with object-name labels overlaid) and reimagines it as a finished image. Label overlays let the model ground parts of the sketch to specific concepts.

| Endpoint | Notes |
|----------|-------|
| Nano Banana / Nano Banana Pro / Nano Banana 2 | Google's image-edit models |
| GPT Image 1.5 Edit | OpenAI's image-edit |
| Seedream 4.5 Edit / Seedream 5 Lite Edit | ByteDance's image-edit |

#### Render-to-Image

<!-- video: render-to-image -->

Renders the scene normally and refines the result with img2img. A strength slider controls how far the model drifts from the input render.

| Endpoint | Notes |
|----------|-------|
| Nano Banana / Nano Banana Pro / Nano Banana 2 | Image-edit style |
| Z-Image Turbo / FLUX.1 [dev] / FLUX.2 Klein 9B | Img2img with strength control |

---

### Video Rendering (Neural Render)

Same controller as image rendering, but the mode switcher is set to **Video**. Renders an animation sequence as depth or edges, then generates a video conditioned on that sequence.

#### Depth-to-Video

<!-- video: depth-to-video -->

Exports a depth animation across the scene's frame range and generates a depth-guided video. Optionally supply a first-frame reference image.

| Endpoint | Notes |
|----------|-------|
| LTX-2 19B / LTX-2 19B Distilled | Open-weight, fast |
| LTX 2.3 22B Ref V2V / LTX 2.3 22B Distilled Ref V2V | Newer LTX with reference-image support |
| Wan-VACE 14B | Good at natural motion |
| Wan Fun 2.2 A14B | Stylized |

#### Edge-to-Video

<!-- video: edge-to-video -->

Canny edges are computed per frame (in parallel threads) and fed to the model as structural conditioning.

| Endpoint | Notes |
|----------|-------|
| LTX-2 19B / LTX-2 19B Distilled | |
| LTX 2.3 22B Ref V2V / LTX 2.3 22B Distilled Ref V2V | Supports a reference image |

Video results import into the Video Sequence Editor. The addon auto-disables `scene.render.use_sequencer` so F12 keeps rendering the 3D view, and pops up a notification when the clip lands.

---

## Video Editor Workflows

Available in the Video Sequence Editor sidebar under the **fal.ai** tab. Results drop in as VSE strips at the current frame and are scaled to the scene's target resolution.

### Audio

One controller, three modes.

#### Text-to-Speech (Presets)

<!-- video: tts-presets -->

Generate speech from text using a named preset voice.

| Endpoint | Notes |
|----------|-------|
| ElevenLabs TTS Turbo v2.5 / v3 | Broad voice catalog |
| MiniMax Speech Turbo / 2.8 HD | |
| Kokoro | Open-weight |
| xAI TTS / Gemini Flash TTS / Inworld TTS | |

#### Text-to-Speech (Voice Clone)

<!-- video: tts-voice-clone -->

Same catalog (for endpoints that support it) but conditioned on a reference audio file — the model clones that voice.

| Endpoint | Notes |
|----------|-------|
| ElevenLabs / MiniMax / others | Any endpoint in the TTS catalog that accepts a voice reference |

#### Text-to-SFX

<!-- video: text-to-sfx -->

Generate sound effects from a text description.

| Endpoint | Notes |
|----------|-------|
| ElevenLabs Sound Effects v2 | |
| CassetteAI SFX | |

#### Text-to-Music

<!-- video: text-to-music -->

Generate music from a text prompt with duration control.

| Endpoint | Notes |
|----------|-------|
| ElevenLabs Music | |
| MiniMax Music 2.6 | |
| Stable Audio 2.5 | |
| CassetteAI Music | |

---

### Video

One controller, two modes. Before submitting a video job you'll see a confirm dialog with the effective size, duration, and cost-relevant settings.

#### Text-to-Video

<!-- video: text-to-video -->

Generate a video clip directly from a prompt.

| Endpoint | Notes |
|----------|-------|
| LTX-2 19B / LTX-2 19B Distilled | |
| LTX 2.3 22B / LTX 2.3 22B Distilled | |
| Seedance 2.0 / Seedance 2.0 Fast | |
| Kling v3 Standard / Kling v3 Pro | |
| Veo 3.1 / Veo 3.1 Fast | |
| Wan 2.2 / Wan 2.2 Turbo / Wan 2.7 | |
| Sora 2 | |

#### Image-to-Video

<!-- video: image-to-video -->

Animate a still image. Same catalog of video endpoints (those that support image conditioning).

| Endpoint | Notes |
|----------|-------|
| Any video endpoint with `image_url` support | |

---

## Shared Workflows

These appear in both the 3D Viewport sidebar and the VSE sidebar with shared config.

### Upscale Image

<!-- video: upscale-image -->

Upscale an image from a file on disk, the current render result, or a texture slot on the active object.

| Endpoint | Notes |
|----------|-------|
| SeedVR2 9B | Highest quality |
| AuraSR | Fast 4x |
| Clarity Upscaler | Detail-preserving |

### Upscale Video

<!-- video: upscale-video -->

Upscale a video file on disk or from the VSE.

| Endpoint | Notes |
|----------|-------|
| SeedVR2 9B | |
| Topaz Video | |

---

## Preferences

`Edit → Preferences → Add-ons → fal.ai — AI Generation Suite`:

- **API Key** — your [fal.ai](https://fal.ai) key (required)
- **Output Directory** — where generated files are saved
- **Auto-Import** — whether results are imported into the active scene automatically

## Advanced Parameters

Every workflow has a collapsible **Advanced Parameters** section that lets you set arbitrary key/value pairs on the request. Useful when fal ships a new endpoint option before the addon's UI catches up — just add it by name. Values are typed (string / int / float / bool / JSON).

## Requirements

- Blender 4.2+ (works on 4.x and 5.x)
- A [fal.ai](https://fal.ai) API key

## Installation

### From Release (coming soon)

1. Download the latest `.zip` from Releases
2. In Blender: `Edit → Preferences → Add-ons → Install from Disk`
3. Select the `.zip` file
4. Enable **fal.ai — AI Generation Suite**
5. Set your API key in the addon preferences

### Development Install

```bash
git clone https://github.com/painebenjamin/fal-blender.git
cd fal-blender

# Download wheels and generate blender_manifest.toml
make all

# Option A: symlink into Blender's extensions directory
ln -s $(pwd) ~/.config/blender/4.5/extensions/fal_ai

# Option B: zip and install via Blender preferences
zip -r fal_ai.zip . -x ".*" -x "__pycache__/*" -x "scripts/*" -x "tests/*"
```

## Architecture

```
controllers/          Blender-side workflows (UI, operators, properties)
  base.py             FalController base class and registration
  operators.py        FalOperator base class (background job submission)
  ui.py               FalControllerPanel (declarative field layout)
  advanced_params.py  Key/value override UIList shared across controllers
  audio/              TTS (preset + clone), SFX, Music (VSE)
  generate_3d/        Text/Image-to-3D (3D Viewport)
  material/           Text-to-Material, Image-to-Maps, Tiling (3D Viewport)
  render/             Depth / Edge / Sketch / Refine modes + Video (3D Viewport)
  upscale/            Image and video upscaling (shared: 3D + VSE)
  video/              Text/Image-to-Video (VSE)

models/               fal.ai endpoint definitions and parameter builders
  base.py             FalModel, VisualFalModel, AudioFalModel, VideoFalModel
  audio_generation/   Speech, SFX, music
  image_generation/   Depth / edge / sketch / refine endpoints
  image_processing/   Image upscaling
  material_generation/ Material, PBR estimation, tiling
  mesh_generation/    Text-to-3D, image-to-3D
  video_generation/   Text/image-to-video, depth/edge video
  video_processing/   Video upscaling

app.py                Panel registration for 3D and VSE sidebars
job_queue.py          Async FalJob / JobManager (threads + bpy timer)
importers.py          GLB/OBJ import, texture application, VSE strip helpers
preferences.py        API key, output dir, auto-import
utils.py              Upload/download, compositor snapshot/restore, fonts
```

Design notes:

- **Controller / Model separation.** Controllers handle Blender-side UI, operators, and scene interaction. Models define the fal.ai endpoint URL and translate UI params into the endpoint's schema. Adding a new endpoint is usually a single new `FalModel` subclass.
- **Declarative panels.** `FalControllerPanel` drives field layout, conditional visibility, and grouping from lists and lambdas — no manual `draw()` per workflow. Conditionals key off the selected endpoint's `ui_parameter_map`, so fields show up only when the current endpoint actually supports them.
- **Async job queue.** API calls run in background threads via `fal_client.subscribe()`. A `bpy.app.timers` loop polls for completion, keeping Blender's UI responsive.
- **Dual-context panels.** Controllers declare `panel_3d`, `panel_vse`, or both and auto-register in the appropriate editor sidebar.

## Tests

```bash
cd fal-blender
./tests/run_tests.sh
```

Model tests don't require Blender; they exercise the `FalModel.parameters()` builders and the per-endpoint `ui_parameter_map` forwarding.

## Planned

- Image-to-Grease Pencil-to-Curves (vector workflow)
- Multi-Image-to-3D pipeline (multi-angle capture to mesh)
- Real-time neural rendering preview
- LoRA support for consistent styling

## License

GPL-3.0-or-later — Copyright 2026 Features and Labels, Inc.

---

Built with love by Benjamin Paine for [fal.ai](https://fal.ai)
