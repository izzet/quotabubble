from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.platform.windows import configure_window, is_packaged, set_launch_at_login
else:
    if sys.platform == "darwin":
        from quotabubble.platform.macos import configure_window, set_launch_at_login
    else:
        from quotabubble.platform.linux import configure_window, set_launch_at_login

    def is_packaged() -> bool:
        return False


__all__ = ["configure_window", "is_packaged", "set_launch_at_login"]
