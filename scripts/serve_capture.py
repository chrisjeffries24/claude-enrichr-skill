#!/usr/bin/env python3
"""
Serve an unzipped Enrichr rebuild_brief capture over HTTP so you can open it
in a browser and verify/debug it — after first applying the SPA dynamic-import
fix (see fix_dynamic_imports.py) so bundled apps don't 404 on their own chunks.

Usage:
    python serve_capture.py <capture-dir> [port]

Example:
    python serve_capture.py site_capture 8811
    # then open http://localhost:8811

This is a convenience wrapper: it runs the import fix against
<capture-dir>/assets/js if that directory exists, then starts a plain static
file server rooted at <capture-dir>. Stop it with Ctrl+C.
"""
import http.server
import functools
import socketserver
import sys
from pathlib import Path

# Reuse the import-fix logic from the sibling script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import fix_dynamic_imports
except Exception:
    fix_dynamic_imports = None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    capture_dir = Path(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8811

    if not capture_dir.is_dir():
        print(f"Not a directory: {capture_dir}")
        sys.exit(1)

    js_dir = capture_dir / "assets" / "js"
    if js_dir.is_dir() and fix_dynamic_imports is not None:
        print("Applying SPA dynamic-import fix...")
        sys.argv = ["fix_dynamic_imports", str(js_dir)]
        try:
            fix_dynamic_imports.main()
        except SystemExit:
            pass
        print()
    elif js_dir.is_dir():
        print("(fix_dynamic_imports.py not importable; serving without the import fix)\n")

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(capture_dir)
    )
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving {capture_dir} at http://localhost:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
