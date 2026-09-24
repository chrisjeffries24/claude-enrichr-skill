#!/usr/bin/env python3
"""
Fix a common breakage in Enrichr's rebuild_brief captures of bundled SPAs
(Nuxt, Next, Vite, etc.): the top-level HTML gets its asset URLs rewritten to
Enrichr's hash-prefixed local names (e.g. "59b7c5ed9e-Bmjs4s05.js"), but
dynamic import() calls *inside* those JS chunks still reference the
original bare hashed filename ("./Bmjs4s05.js"). When you serve the capture
locally, the bare name 404s and the app's own error boundary usually masks
this as a vague hydration/runtime error instead of a clear 404.

This script finds every bare import specifier referenced inside the
downloaded JS files and creates a same-content copy under that bare name,
so relative imports resolve. Run it once against a capture's assets/js/
directory (or wherever the JS bundle files live) after unzipping.

Usage:
    python fix_dynamic_imports.py <path-to-js-directory>
"""
import re
import shutil
import sys
from pathlib import Path

IMPORT_RE = re.compile(r'["\']\.\/([A-Za-z0-9_\-\.]+\.js)["\']')


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    js_dir = Path(sys.argv[1])
    if not js_dir.is_dir():
        print(f"Not a directory: {js_dir}")
        sys.exit(1)

    js_files = list(js_dir.glob("*.js"))
    existing_names = {f.name for f in js_files}

    referenced = set()
    for f in js_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in IMPORT_RE.finditer(text):
            referenced.add(m.group(1))

    created = []
    still_missing = []
    for bare_name in sorted(referenced):
        if bare_name in existing_names:
            continue
        # Enrichr renames files as "<hash>-<original-name>", so find the file
        # that ends with "-<bare_name>".
        candidates = [f for f in js_files if f.name.endswith(f"-{bare_name}")]
        if candidates:
            src = candidates[0]
            dst = js_dir / bare_name
            shutil.copyfile(src, dst)
            created.append((src.name, bare_name))
        else:
            still_missing.append(bare_name)

    print(f"Scanned {len(js_files)} JS files, found {len(referenced)} bare import specifiers.")
    if created:
        print(f"\nCreated {len(created)} bare-named copies so relative imports resolve:")
        for src, dst in created:
            print(f"  {dst}  (copy of {src})")
    if still_missing:
        print(f"\n{len(still_missing)} referenced chunk(s) were never downloaded - these are lazy")
        print("chunks the capture never triggered (a feature/route not exercised during")
        print("capture). They'll 404 if that code path runs; that's expected for a static")
        print("capture, not a bug in this fix:")
        for name in still_missing:
            print(f"  {name}")
    if not created and not still_missing:
        print("No bare-name mismatches found - this capture may not need this fix.")


if __name__ == "__main__":
    main()
