# fal.ai Blender Extension

AI-powered textures, 3D models, rendering, video and audio — directly inside Blender.

**This is very much so a work-in-progress and not officially supported. If/when this is officially supported, the repository will be moved under fal's GitHub organization.**

## Features

The addon is split across two editor contexts: the **3D Viewport** (for scene-oriented workflows) and the **Video Sequence Editor** (for timeline-oriented workflows). Each context has its own set of controllers selectable from a workflow dropdown.

### 3D Viewport Workflows

| Workflow | Description | Endpoints |
|----------|-------------|-----------|
| **Material** | Generate PBR materials from prompts, estimate PBR maps from images, or create tiling textures. Outputs a full Principled BSDF material. | Patina, Z-Image Turbo Tiling |
| **3D Generation** | Text-to-3D and image-to-3D mesh generation. Imports GLB at the 3D cursor. | Meshy v5, Meshy v6 |
| **Neural Render: Depth** | Render a Mist depth pass, then generate an AI image guided by scene depth. | FLUX.1 Dev ControlNet, Z-Image Turbo ControlNet |
| **Neural Render: Sketch** | Render a Freestyle line drawing, optionally overlay object name labels, then AI reimagines the sketch. | Nano Banana, Nano Banana Pro, Nano Banana 2 |
| **Neural Render: Refine** | Render the scene normally, then refine the result via image-to-image with an adjustable strength parameter. | Nano Banana, Nano Banana Pro, Nano Banana 2, Z-Image Turbo, FLUX.1 Dev, FLUX.2 Klein 9B |
| **Upscale** | Upscale images (from file, render, or texture) or video files. | SeedVR2 9B, AuraSR, Clarity (image); SeedVR2 9B (video) |
| **Depth Video** | Render a depth animation sequence from the scene, then generate a depth-conditioned video. Optionally supply a first-frame reference image. | Wan-VACE 14B, Wan-Fun 2.2A 14B, LTX-2 19B, LTX-2 19B Distilled |

### VSE Workflows

| Workflow | Description | Endpoints |
|----------|-------------|-----------|
| **Video** | Text-to-video and image-to-video generation. Adds result as a VSE strip. | Kling 3.0 Pro, Wan 2.1 |
| **Audio: TTS** | Text-to-speech with voice presets. | ElevenLabs TTS Turbo v2.5 |
| **Audio: SFX** | Generate sound effects from text descriptions. | ElevenLabs Sound Effects v2 |
| **Audio: Music** | Generate music from prompts. | ElevenLabs Music |

### Planned

- Image-to-Grease Pencil-to-Curves (vector workflow)
- Multi-Image-to-3D pipeline (multi-angle capture to mesh)
- Real-time neural rendering preview
- LoRA support for consistent styling
- Voice cloning for TTS

## Architecture

```
controllers/          Blender-side workflows (UI, operators, properties)
  base.py             FalController base class and registration
  operators.py        FalOperator base class (background job submission)
  ui.py               FalControllerPanel (declarative field layout)
  audio/              TTS, SFX, Music (VSE only)
  generate_3d/        Text/Image-to-3D (3D only)
  material/           PBR material generation (3D only)
  render/             Depth, Sketch, Refine, Edge modes + Video (3D only)
  upscale/            Image and video upscaling (3D only)
  video/              Text/Image-to-Video (VSE only)

models/               fal.ai endpoint definitions and parameter builders
  base.py             FalModel, VisualFalModel, AudioFalModel
  audio_generation/   ElevenLabs speech, SFX, music
  image_generation/   Depth-guided, sketch-guided, refinement
  image_processing/   Image upscaling
  material_generation/ Material, PBR estimation, tiling
  mesh_generation/    Text-to-3D, image-to-3D
  video_generation/   Text/image-to-video, depth video
  video_processing/   Video upscaling

app.py                Main panels and scene properties for 3D and VSE
job_queue.py          Async FalJob / JobManager (background threads + bpy timer)
importers.py          GLB import, texture application, VSE strip helpers
preferences.py        API key and output directory settings
utils.py              Upload/download, compositor snapshot/restore, fonts
```

Key design points:

- **Controller / Model separation** — Controllers handle Blender-side UI, operators, and scene interaction. Models define fal.ai endpoint URLs and parameter translation. Adding a new endpoint is typically a single new `FalModel` subclass.
- **Declarative panel UI** — `FalControllerPanel` drives field layout, conditional visibility, and grouping from simple lists and lambdas — no manual `draw()` code per workflow.
- **Async job queue** — API calls run in background threads via `fal_client.subscribe()`. A `bpy.app.timers` loop polls for completion, keeping the UI responsive.
- **Multi-endpoint selection** — Every workflow exposes a dropdown to choose which model/endpoint to use.
- **Dual-context panels** — Controllers declare `panel_3d`, `panel_vse`, or both, and are automatically registered in the appropriate editor sidebar.

## Requirements

- Blender 4.2+ (supports both Blender 4.x and 5.x)
- A [fal.ai](https://fal.ai) API key

## Installation

### From Release (coming soon)
1. Download the latest `.zip` from Releases
2. In Blender: Edit → Preferences → Add-ons → Install from Disk
3. Select the `.zip` file
4. Enable "fal.ai — AI Generation Suite"
5. Set your API key in the addon preferences

### Development Install
```bash
# Clone
git clone https://github.com/painebenjamin/fal-blender.git
cd fal-blender

# Download wheels and generate blender_manifest.toml from blender_manifest.toml.template
make all

# Option A: Symlink into Blender's extensions directory
ln -s $(pwd) ~/.config/blender/4.5/extensions/fal_ai

# Option B: Zip and install
zip -r fal_ai.zip . -x ".*" -x "__pycache__/*" -x "scripts/*" -x "tests/*"
# Then install via Blender preferences
```

## Usage

1. Open the **3D Viewport** sidebar (press `N`) or the **Video Sequence Editor** sidebar
2. Click the **fal.ai** tab
3. Select a workflow from the dropdown
4. Configure parameters and click **Generate**
5. Monitor progress in the **Active Jobs** sub-panel

## License

GPL-3.0-or-later — Copyright 2026 Features and Labels, Inc.

---

Built with love by Benjamin Paine for [fal.ai](https://fal.ai)
