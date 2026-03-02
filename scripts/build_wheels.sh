#!/usr/bin/env bash
# Download fal-client and dependencies as wheels for bundling.
# Run from the repo root: bash scripts/build_wheels.sh
set -euo pipefail

WHEEL_DIR="wheels"
rm -rf "$WHEEL_DIR"
mkdir -p "$WHEEL_DIR"

# Target platforms for Blender extension
PLATFORMS=(
    "manylinux2014_x86_64"
    "macosx_11_0_arm64"
    "macosx_11_0_x86_64"
    "win_amd64"
)

echo "=== Downloading pure-Python wheels ==="
pip download \
    --dest "$WHEEL_DIR" \
    --only-binary :all: \
    --python-version 3.11 \
    --no-deps \
    fal-client httpx httpx-sse httpcore certifi idna sniffio anyio h11 websockets

echo ""
echo "=== Downloading platform-specific wheels (msgpack) ==="
for plat in "${PLATFORMS[@]}"; do
    echo "  → $plat"
    pip download \
        --dest "$WHEEL_DIR" \
        --only-binary :all: \
        --platform "$plat" \
        --python-version 3.11 \
        --no-deps \
        msgpack || echo "    (skipped $plat)"
done

echo ""
echo "=== Wheels downloaded ==="
ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "(no wheels found)"

echo ""
echo "=== Generating manifest wheel entries ==="
echo "# Add these to blender_manifest.toml under [wheels]:"
echo 'wheels = ['
for whl in "$WHEEL_DIR"/*.whl; do
    [ -f "$whl" ] && echo "  \"./$whl\","
done
echo ']'
