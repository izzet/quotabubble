from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.platform.windows import configure_window, set_launch_at_login
elif sys.platform == "darwin":
    from quotabubble.platform.macos import configure_window, set_launch_at_login
else:
    from quotabubble.platform.linux import configure_window, set_launch_at_login

__all__ = ["configure_window", "set_launch_at_login"]
