import sys
import os
import shutil



HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RENDER_DIR = os.path.join(ROOT, "controllers", "render")

TEST_IMAGE = os.path.join(HERE, "test_image.jpg")
TEST_EDGE_OUTPUT = os.path.join(HERE, "test_edge_output.png")
BASELINE_EDGE_OUTPUT = os.path.join(HERE, "baseline_edge_output.png")
FIXED_EDGE_OUTPUT = os.path.join(HERE, "fixed_edge_output.png")
COMPARISON_GRID = os.path.join(HERE, "comparison_grid.png")

# ---------------------------------------------------------------------------
# Canny edge detection (pure NumPy — no OpenCV / scikit-image)
# ---------------------------------------------------------------------------
def render_to_canny(
    render_path: str,
    width: int,
    height: int,
    low_threshold: int = 100,
    high_threshold: int = 200,
    sigma: float = 1.0,
) -> None:
    """Convert a rendered image to Canny edge detection output.

    Pure NumPy implementation — no OpenCV or scikit-image needed.
    Overwrites the image at render_path with white edges on black background.
    """
    from PIL import Image
    import numpy as np

    img = Image.open(render_path).convert("L")
    pixels = np.array(img, dtype=np.float64)

    # 1. Optional Gaussian blur (separable convolution with reflect padding —
    #    zero-padding here was producing a strong edge ring around the image)
    if sigma > 0:
        size = int(2 * np.ceil(2 * sigma) + 1)
        x = np.arange(size) - size // 2
        kernel = np.exp(-x**2 / (2 * sigma**2))
        kernel /= kernel.sum()
        pad = size // 2

        padded_h = np.pad(pixels, ((0, 0), (pad, pad)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="valid"), axis=1, arr=padded_h
        )
        padded_v = np.pad(blurred, ((pad, pad), (0, 0)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda col: np.convolve(col, kernel, mode="valid"), axis=0, arr=padded_v
        )
    else:
        blurred = pixels

    # 2. Sobel gradients via array slicing
    Gx = (
        -1 * blurred[:-2, :-2] + 1 * blurred[:-2, 2:]
        - 2 * blurred[1:-1, :-2] + 2 * blurred[1:-1, 2:]
        - 1 * blurred[2:, :-2] + 1 * blurred[2:, 2:]
    )
    Gy = (
        1 * blurred[:-2, :-2] + 2 * blurred[:-2, 1:-1] + 1 * blurred[:-2, 2:]
        - 1 * blurred[2:, :-2] - 2 * blurred[2:, 1:-1] - 1 * blurred[2:, 2:]
    )

    # L1 magnitude (matches cv2 default; recovers low-contrast edges that L2 misses)
    magnitude = np.abs(Gx) + np.abs(Gy)
    direction = np.arctan2(Gy, Gx)

    # 3. Non-maximum suppression (vectorized)
    angle = direction * 180.0 / np.pi
    angle[angle < 0] += 180

    # Quantize to 4 directions: 0=horiz, 1=diag45, 2=vert, 3=diag135
    d = np.round(angle / 45.0) % 4

    h, w = magnitude.shape
    suppressed = np.zeros_like(magnitude)

    # Pad magnitude with edge replication so border pixels aren't auto-suppressed
    mag_pad = np.pad(magnitude, 1, mode="edge")

    # Direction 0 (horizontal): compare with left/right neighbors
    mask0 = d == 0
    q0 = mag_pad[1:h + 1, 2:w + 2]  # right
    r0 = mag_pad[1:h + 1, 0:w]      # left

    # Direction 1 (diagonal 45°): compare with bottom-left/top-right
    mask1 = d == 1
    q1 = mag_pad[2:h + 2, 0:w]      # bottom-left
    r1 = mag_pad[0:h, 2:w + 2]      # top-right

    # Direction 2 (vertical): compare with top/bottom neighbors
    mask2 = d == 2
    q2 = mag_pad[2:h + 2, 1:w + 1]  # below
    r2 = mag_pad[0:h, 1:w + 1]      # above

    # Direction 3 (diagonal 135°): compare with top-left/bottom-right
    mask3 = d == 3
    q3 = mag_pad[0:h, 0:w]          # top-left
    r3 = mag_pad[2:h + 2, 2:w + 2]  # bottom-right

    for mask, q, r in [(mask0, q0, r0), (mask1, q1, r1),
                       (mask2, q2, r2), (mask3, q3, r3)]:
        keep = mask & (magnitude >= q) & (magnitude >= r)
        suppressed[keep] = magnitude[keep]

    # 4. Double threshold + hysteresis
    strong_val = 255.0
    weak_val = 50.0
    result = np.zeros_like(suppressed)
    strong_mask = suppressed >= high_threshold
    weak_mask = (suppressed >= low_threshold) & (~strong_mask)
    result[strong_mask] = strong_val
    result[weak_mask] = weak_val

    # Hysteresis: iteratively promote weak pixels adjacent to strong ones
    # using morphological dilation of the strong mask
    promoted = strong_mask.copy()
    while True:
        # Dilate: any weak pixel with a strong neighbor becomes strong
        dilated = np.zeros_like(promoted)
        dilated[1:, :] |= promoted[:-1, :]
        dilated[:-1, :] |= promoted[1:, :]
        dilated[:, 1:] |= promoted[:, :-1]
        dilated[:, :-1] |= promoted[:, 1:]
        dilated[1:, 1:] |= promoted[:-1, :-1]
        dilated[1:, :-1] |= promoted[:-1, 1:]
        dilated[:-1, 1:] |= promoted[1:, :-1]
        dilated[:-1, :-1] |= promoted[1:, 1:]

        new_strong = weak_mask & dilated & (~promoted)
        if not new_strong.any():
            break
        promoted |= new_strong

    result[promoted] = strong_val
    result[~promoted] = 0

    # Pad result back to original size (Sobel shrinks by 1 on each edge);
    # replicate the outermost row/col into the 1-pixel border so it doesn't
    # show up as a dark frame.
    res = result.astype(np.uint8)
    full = np.zeros((height, width), dtype=np.uint8)
    full[1:1 + res.shape[0], 1:1 + res.shape[1]] = res
    full[0, 1:1 + res.shape[1]] = res[0, :]
    full[-1, 1:1 + res.shape[1]] = res[-1, :]
    full[:, 0] = full[:, 1]
    full[:, -1] = full[:, -2]

    Image.fromarray(full).convert("RGB").save(render_path)

def render_to_canny_opencv(
    render_path: str,
    low_threshold: int = 100,
    high_threshold: int = 200,
) -> None:
    """Convert a rendered image to Canny edge detection output using OpenCV."""
    import cv2
    img = cv2.imread(render_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.Canny(img, low_threshold, high_threshold)
    cv2.imwrite(render_path, img)


# ---------------------------------------------------------------------------
# Fixed Canny — addresses three root causes vs the original:
#   1. zero-padded Gaussian convolution → reflect padding (kills border ring)
#   2. L2 magnitude (np.hypot) → L1 magnitude (matches cv2 default, +detail)
#   3. sigma=1.4 over-blurs smooth surfaces → default sigma=1.0; sigma=0 skips
# Also pads result back via edge-replication instead of leaving a zero border.
# ---------------------------------------------------------------------------
def render_to_canny_fixed(
    render_path: str,
    width: int,
    height: int,
    low_threshold: int = 100,
    high_threshold: int = 200,
    sigma: float = 1.0,
) -> None:
    from PIL import Image
    import numpy as np

    img = Image.open(render_path).convert("L")
    pixels = np.array(img, dtype=np.float64)

    # 1. Optional Gaussian blur with reflect padding
    if sigma > 0:
        size = int(2 * np.ceil(2 * sigma) + 1)
        x = np.arange(size) - size // 2
        kernel = np.exp(-x ** 2 / (2 * sigma ** 2))
        kernel /= kernel.sum()
        pad = size // 2

        # Horizontal pass with reflect padding
        padded_h = np.pad(pixels, ((0, 0), (pad, pad)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="valid"), axis=1, arr=padded_h
        )
        # Vertical pass with reflect padding
        padded_v = np.pad(blurred, ((pad, pad), (0, 0)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda col: np.convolve(col, kernel, mode="valid"), axis=0, arr=padded_v
        )
    else:
        blurred = pixels

    # 2. Sobel gradients via array slicing
    Gx = (
        -1 * blurred[:-2, :-2] + 1 * blurred[:-2, 2:]
        - 2 * blurred[1:-1, :-2] + 2 * blurred[1:-1, 2:]
        - 1 * blurred[2:, :-2] + 1 * blurred[2:, 2:]
    )
    Gy = (
        1 * blurred[:-2, :-2] + 2 * blurred[:-2, 1:-1] + 1 * blurred[:-2, 2:]
        - 1 * blurred[2:, :-2] - 2 * blurred[2:, 1:-1] - 1 * blurred[2:, 2:]
    )

    # L1 magnitude (matches cv2 default; recovers low-contrast edges that L2 drops)
    magnitude = np.abs(Gx) + np.abs(Gy)
    direction = np.arctan2(Gy, Gx)

    # 3. Non-maximum suppression (vectorized)
    angle = direction * 180.0 / np.pi
    angle[angle < 0] += 180
    d = np.round(angle / 45.0) % 4

    h, w = magnitude.shape
    suppressed = np.zeros_like(magnitude)

    # Pad with edge replication so border pixels aren't artificially suppressed
    mag_pad = np.pad(magnitude, 1, mode="edge")

    mask0 = d == 0
    q0 = mag_pad[1:h + 1, 2:w + 2]
    r0 = mag_pad[1:h + 1, 0:w]

    mask1 = d == 1
    q1 = mag_pad[2:h + 2, 0:w]
    r1 = mag_pad[0:h, 2:w + 2]

    mask2 = d == 2
    q2 = mag_pad[2:h + 2, 1:w + 1]
    r2 = mag_pad[0:h, 1:w + 1]

    mask3 = d == 3
    q3 = mag_pad[0:h, 0:w]
    r3 = mag_pad[2:h + 2, 2:w + 2]

    for mask, q, r in [(mask0, q0, r0), (mask1, q1, r1),
                       (mask2, q2, r2), (mask3, q3, r3)]:
        keep = mask & (magnitude >= q) & (magnitude >= r)
        suppressed[keep] = magnitude[keep]

    # 4. Double threshold + hysteresis
    strong_mask = suppressed >= high_threshold
    weak_mask = (suppressed >= low_threshold) & (~strong_mask)

    promoted = strong_mask.copy()
    while True:
        dilated = np.zeros_like(promoted)
        dilated[1:, :] |= promoted[:-1, :]
        dilated[:-1, :] |= promoted[1:, :]
        dilated[:, 1:] |= promoted[:, :-1]
        dilated[:, :-1] |= promoted[:, 1:]
        dilated[1:, 1:] |= promoted[:-1, :-1]
        dilated[1:, :-1] |= promoted[:-1, 1:]
        dilated[:-1, 1:] |= promoted[1:, :-1]
        dilated[:-1, :-1] |= promoted[1:, 1:]

        new_strong = weak_mask & dilated & (~promoted)
        if not new_strong.any():
            break
        promoted |= new_strong

    result = np.where(promoted, 255, 0).astype(np.uint8)

    # Pad back to original size by replicating edge rows/cols (no zero border)
    full = np.zeros((height, width), dtype=np.uint8)
    full[1:1 + result.shape[0], 1:1 + result.shape[1]] = result
    # Replicate first/last valid rows and cols into the 1-pixel border
    full[0, 1:1 + result.shape[1]] = result[0, :]
    full[-1, 1:1 + result.shape[1]] = result[-1, :]
    full[:, 0] = full[:, 1]
    full[:, -1] = full[:, -2]

    Image.fromarray(full).convert("RGB").save(render_path)


def make_grid(paths_with_labels, out_path):
    """Compose a labeled grid from a list of (label, path) pairs."""
    from PIL import Image, ImageDraw, ImageFont
    imgs = [Image.open(p).convert("RGB") for _, p in paths_with_labels]
    w, h = imgs[0].size
    label_h = 36
    cols = len(imgs)
    grid = Image.new("RGB", (w * cols, h + label_h), (32, 32, 32))
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for i, (label, _) in enumerate(paths_with_labels):
        grid.paste(imgs[i], (i * w, label_h))
        draw.text((i * w + 12, 6), label, fill=(255, 255, 255), font=font)
    grid.save(out_path)


if __name__ == "__main__":
    for p in (TEST_EDGE_OUTPUT, BASELINE_EDGE_OUTPUT, FIXED_EDGE_OUTPUT, COMPARISON_GRID):
        if os.path.exists(p):
            os.remove(p)

    shutil.copy(TEST_IMAGE, TEST_EDGE_OUTPUT)
    shutil.copy(TEST_IMAGE, BASELINE_EDGE_OUTPUT)
    shutil.copy(TEST_IMAGE, FIXED_EDGE_OUTPUT)
    render_to_canny(TEST_EDGE_OUTPUT, 640, 852)
    render_to_canny_opencv(BASELINE_EDGE_OUTPUT)
    render_to_canny_fixed(FIXED_EDGE_OUTPUT, 640, 852)

    make_grid(
        [
            ("input",          TEST_IMAGE),
            ("current (ours)", TEST_EDGE_OUTPUT),
            ("fixed (ours)",   FIXED_EDGE_OUTPUT),
            ("cv2 baseline",   BASELINE_EDGE_OUTPUT),
        ],
        COMPARISON_GRID,
    )
    print(f"wrote {COMPARISON_GRID}")