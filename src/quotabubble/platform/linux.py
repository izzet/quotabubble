from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir
from PySide6.QtWidgets import QWidget

from quotabubble.platform.launch import launch_command
from quotabubble.utils import write_text_atomic

AUTOSTART_FILE = Path(user_config_dir()) / "autostart" / "quotabubble.desktop"


def configure_window(widget: QWidget) -> None:
    return None


def set_launch_at_login(enabled: bool) -> None:
    if enabled:
        write_text_atomic(AUTOSTART_FILE, _desktop_entry())
    elif AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()


def _desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=QuotaBubble\n"
        f"Exec={launch_command()}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
