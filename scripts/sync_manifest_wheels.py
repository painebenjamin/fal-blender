#!/usr/bin/env python3
"""Render blender_manifest.toml from the template and wheels/*.whl."""

from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "blender_manifest.toml.template"
OUTPUT = REPO_ROOT / "blender_manifest.toml"
WHEELS_DIR = REPO_ROOT / "wheels"


def replace_wheels_block(text: str, entries: list[str]) -> str:
    m = re.search(r"^wheels\s*=\s*\[", text, re.MULTILINE)
    if not m:
        raise ValueError(
            "Could not find a top-level wheels = [ in blender_manifest.toml.template"
        )

    start = m.start()
    i = m.end() - 1
    assert text[i] == "[", "expected '[' after wheels ="
    depth = 0
    j = i
    while j < len(text):
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                inner = "".join(f'  "{e}",\n' for e in entries)
                new_block = f"wheels = [\n{inner}]"
                return text[:start] + new_block + text[j + 1 :]
        j += 1
    raise ValueError("Unclosed wheels = [ ... ] in blender_manifest.toml.template")


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"Missing {TEMPLATE}", file=sys.stderr)
        return 1

    whl_files = sorted(glob.glob(str(WHEELS_DIR / "*.whl")))
    wheel_paths = [f"./wheels/{Path(p).name}" for p in whl_files]

    text = TEMPLATE.read_text(encoding="utf-8")
    try:
        updated = replace_wheels_block(text, wheel_paths)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    OUTPUT.write_text(updated, encoding="utf-8")
    print(f"Wrote {OUTPUT} from {TEMPLATE.name} ({len(wheel_paths)} wheel(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
