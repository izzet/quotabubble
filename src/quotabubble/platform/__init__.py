from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.platform.windows import configure_window
elif sys.platform == "darwin":
    from quotabubble.platform.macos import configure_window
else:
    from quotabubble.platform.linux import configure_window

__all__ = ["configure_window"]
