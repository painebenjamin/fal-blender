# fal.ai Blender Extension

AI-powered textures, 3D models, rendering, video and audio — directly inside Blender.

> **Status:** Early development (Phase 1 MVP)

## Features

### Phase 1 (MVP)
- 🎨 **Text-to-Texture** — Generate textures from prompts, apply to objects
- 🧊 **Text-to-3D** — Generate 3D models from text descriptions
- 🖼️ **Image-to-3D** — Convert images to 3D models

### Planned
- 🎨 Tiled texture generation
- 🧱 PBR material generation (diffuse + normal + roughness + metallic)
- ✏️ Image → Grease Pencil → Curves
- 🖼️ Neural rendering (depth-controlled, sketch-to-render)
- 🎬 AI video generation (including depth-conditioned)
- 🔊 Audio generation (TTS, SFX, music)
- ⬆️ AI upscaling (image + video)
- 🔄 3D-to-3D (retexture, remesh)
- ⚡ Real-time neural rendering preview

## Requirements

- Blender 4.2+
- A [fal.ai](https://fal.ai) API key

## Installation

1. Download the latest release `.zip`
2. In Blender: Edit → Preferences → Add-ons → Install from Disk
3. Select the `.zip` file
4. Enable "fal.ai — AI Generation Suite"
5. Set your API key in the addon preferences

## Usage

Open the 3D Viewport sidebar (N key) → **fal.ai** tab.

## Development

```bash
# Clone
git clone https://github.com/fal-ai/fal-blender.git
cd fal-blender

# Download dependency wheels
bash scripts/build_wheels.sh

# Symlink into Blender's extensions directory for development
ln -s $(pwd) ~/.config/blender/4.2/extensions/fal_ai
```

## License

Apache 2.0 — Copyright 2026 Features and Labels, Inc.
