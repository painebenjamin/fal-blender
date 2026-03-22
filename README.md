# fal.ai Blender Extension

AI-powered textures, 3D models, rendering, video and audio — directly inside Blender.

**This is very much so a work-in-progress and not officially supported - many features likely do not work yet. If/when this is officially supported, the repository will be moved under fal's GitHub organization.**

## Features

### ✅ Implemented

| Feature | Description | Endpoints |
|---------|-------------|-----------|
| **Text-to-Texture** | Generate textures from prompts, auto-apply to materials | Nano Banana Pro/2, FLUX, z-image |
| **Text-to-3D** | Generate 3D models from text descriptions | Meshy v6 |
| **Image-to-3D** | Convert images to 3D models | Meshy v5/v6 |
| **AI Upscale (Image)** | Upscale textures and renders | SeedVR2, AuraSR, Clarity |
| **AI Upscale (Video)** | Upscale video files | SeedVR2 Video |
| **Neural Render: Depth** | Render depth pass → depth-controlled image generation | FLUX Depth ControlNet, z-image ControlNet |
| **Neural Render: Sketch** | Render blocky scene → AI reimagines with optional text labels | Nano Banana Pro/2, FLUX |
| **Text-to-Video** | Generate video from text prompts | Kling 3.0 Pro, Wan 2.1 |
| **Image-to-Video** | Animate an image into video | Kling 3.0 Pro, Wan 2.1 |
| **Depth-Cond Video** | Depth sequence → structural video guide | Wan-VACE, Wan-Fun, LTX-2 |
| **TTS** | Text-to-speech with voice presets or voice cloning | (endpoints TBD) |
| **SFX** | Generate sound effects from descriptions | (endpoints TBD) |
| **Music** | Generate music from prompts | (endpoints TBD) |
| **Retexture** | AI retexture existing 3D models | Meshy v5 |
| **Remesh** | AI-powered mesh cleanup | Meshy v5 |

### 🔜 Planned

- Tiled/seamless texture generation (dedicated multi-diffusion endpoint)
- PBR material generation (diffuse + normal + roughness + metallic)
- Image → Grease Pencil → Curves (vector workflow)
- Multi-Image-to-3D pipeline (Qwen multi-angle → Meshy)
- Real-time neural rendering preview
- LoRA support for consistent styling

## Architecture

- **Async job queue** — API calls run in background threads, UI stays responsive
- **Unified resolution interface** — Set pixels, backend handles aspect/resolution vs width/height translation per endpoint
- **Multi-endpoint selection** — Every feature has a dropdown to choose which model to use
- **VSE integration** — Audio and video results can auto-import into the Video Sequence Editor

## Requirements

- Blender 4.5+
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

# Download dependency wheels
bash scripts/build_wheels.sh

# Option A: Symlink into Blender's extensions directory
ln -s $(pwd) ~/.config/blender/4.5/extensions/fal_ai

# Option B: Zip and install
zip -r fal_ai.zip . -x ".*" -x "__pycache__/*" -x "scripts/*" -x "tests/*"
# Then install via Blender preferences
```

## Usage

1. Open the 3D Viewport sidebar (press `N`)
2. Click the **fal.ai** tab
3. Select a feature tab (Texture, 3D, Upscale, Render, Video, Audio, Mesh Ops)
4. Choose an endpoint from the dropdown
5. Fill in the parameters and click Generate

## License

Apache 2.0 — Copyright 2026 Features and Labels, Inc.

---

Built with ❤️ by Benjamin Paine for [fal.ai](https://fal.ai)
