#!/usr/bin/env python3
"""
Pull embedded base64 screenshots out of a saved Enrichr tool-result file
into real PNGs you can open with the Read tool.

Why this exists: rebuild_brief, interact_with_page (capture_screenshots=true),
and take_screenshot can all return results too large for the tool response,
which get saved to a local .txt file with a truncation notice instead. That
file is almost always JSON containing one or more base64 image strings
(under keys like "screenshots", "base64", "screenshot", etc.) — this script
finds every string that looks like base64 image data of meaningful size and
writes each one out as its own .png, regardless of the exact shape of the
JSON (different Enrichr tools nest screenshots differently).

Usage:
    python extract_screenshots.py <path-to-saved-tool-result.txt> <output-dir>
"""
import base64
import json
import sys
from pathlib import Path

MIN_BYTES = 5000  # skip tiny base64 strings that aren't real screenshots


def walk(obj, path, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]", out)
    elif isinstance(obj, str) and len(obj) > MIN_BYTES:
        candidate = obj.split(",", 1)[1] if obj.startswith("data:image") else obj
        try:
            raw = base64.b64decode(candidate, validate=True)
        except Exception:
            return
        # PNG/JPEG magic bytes — skip anything that decoded but isn't an image
        if raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff":
            out.append((path, raw))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(src.read_text(encoding="utf-8"))
    found = []
    walk(data, "root", found)

    if not found:
        print("No embedded images found - this result may not contain screenshots,")
        print("or the JSON structure wasn't recognized. Open the file and check")
        print("manually for a field holding base64 image data.")
        return

    for i, (path, raw) in enumerate(found):
        ext = "png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "jpg"
        out_path = out_dir / f"shot_{i}.{ext}"
        out_path.write_bytes(raw)
        print(f"{out_path}  ({len(raw):,} bytes, from {path})")

    print(f"\nExtracted {len(found)} image(s) to {out_dir}")


if __name__ == "__main__":
    main()
