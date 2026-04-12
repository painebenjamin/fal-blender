#!/usr/bin/env bash
# Download fal-client and dependencies as wheels for bundling.
# Run from the repo root: bash scripts/build_wheels.sh
# Cross-platform downloads use pip's --platform (see Blender manual: Python Wheels).
set -euo pipefail

WHEEL_DIR="${WHEEL_DIR:-wheels}"
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
mkdir -p "$WHEEL_DIR"
# For a clean download directory: `make clean` (removes wheels/) or WHEEL_FRESH=1.
if [ "${WHEEL_FRESH:-0}" != 0 ]; then
    rm -rf "${WHEEL_DIR:?}/"*
fi

# Pip platform tags for binary wheels (Blender 4.5+ uses CPython 3.11+; adjust PYTHON_VERSION if needed).
# manylinux_2_28 matches the Blender docs example; PyPI may emit a compound manylinux tag on the filename.
PLATFORMS=(
    "manylinux_2_28_x86_64"
    "macosx_11_0_arm64"
    "macosx_11_0_x86_64"
    "win_amd64"
    "win_arm64"
)

echo "=== Downloading universal wheels (py3-none-any) ==="
# Omit --platform so pip still prefers py3-none-any for these. Do not list packages here that
# only publish per-platform wheels (e.g. websockets) — those go in the platform loop below.
pip download \
    --dest "$WHEEL_DIR" \
    --only-binary :all: \
    --python-version $PYTHON_VERSION \
    --no-deps \
    fal-client httpx httpx-sse httpcore certifi idna sniffio anyio h11

echo ""
echo "=== Downloading platform-specific wheels (msgpack, Pillow, websockets) ==="
for plat in "${PLATFORMS[@]}"; do
    echo "  → $plat"
    pip download \
        --dest "$WHEEL_DIR" \
        --only-binary :all: \
        --platform "$plat" \
        --python-version $PYTHON_VERSION \
        --no-deps \
        msgpack Pillow websockets || echo "    (skipped $plat)"
done

echo ""
echo "=== Wheels downloaded ==="
ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "(no wheels found)"

echo ""
echo "=== Generating manifest wheel entries ==="
echo "# Run: make sync-manifest  (uses blender_manifest.toml.template)"
echo 'wheels = ['
for whl in "$WHEEL_DIR"/*.whl; do
    [ -f "$whl" ] && echo "  \"./$whl\","
done
echo ']'
