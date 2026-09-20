from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from quotabubble.platform.launch import launch_command

AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "quotabubble.desktop"


def configure_application() -> None:
    return None


def configure_window(widget: QWidget) -> None:
    return None


def set_launch_at_login(enabled: bool) -> None:
    if enabled:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(_desktop_entry(), encoding="utf-8")
    elif AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()


def _desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=QuotaBubble\n"
        f"Exec={launch_command()}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
