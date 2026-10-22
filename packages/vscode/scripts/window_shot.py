# /// script
# requires-python = ">=3.11"
# dependencies = ["pyobjc-framework-Quartz"]
# ///
"""Screenshot of one macOS window, even if other windows cover it.

usage: uv run scripts/window_shot.py "<title or app name substring>" out.png
"""

import subprocess
import sys

import Quartz

title, out = sys.argv[1], sys.argv[2]
windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
ids = [
    w["kCGWindowNumber"]
    for w in windows
    if w.get("kCGWindowLayer") == 0
    and (title in (w.get("kCGWindowName") or "") or title in (w.get("kCGWindowOwnerName") or ""))
]
if not ids:
    sys.exit(f"no window titled like {title!r}")
subprocess.run(["screencapture", "-x", "-o", "-l", str(ids[0]), out], check=True)
