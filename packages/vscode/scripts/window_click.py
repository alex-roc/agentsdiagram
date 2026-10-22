# /// script
# requires-python = ">=3.11"
# dependencies = ["pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""Click inside one macOS window, at a point relative to its top-left corner.

usage: uv run scripts/window_click.py "<title substring>" X Y
A negative X counts from the right edge. The window's app is brought to the front first, so
the click cannot land on another window. Needs the Accessibility permission.
"""

import sys
import time

import AppKit
import Quartz

title, x, y = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
match = [w for w in windows if w.get("kCGWindowLayer") == 0 and title in (w.get("kCGWindowName") or "")]
if not match:
    sys.exit(f"no window titled like {title!r}")
app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(match[0]["kCGWindowOwnerPID"])
app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
time.sleep(0.6)
b = match[0]["kCGWindowBounds"]
point = (b["X"] + (b["Width"] + x if x < 0 else x), b["Y"] + y)
for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
    event = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(0.05)
print(f"clicked {point} in a {b['Width']:.0f}x{b['Height']:.0f} window")
