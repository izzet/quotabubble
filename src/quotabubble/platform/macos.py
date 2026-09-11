from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget

from quotabubble.platform.launch import launch_command

LAUNCH_AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / "com.izzet.quotabubble.plist"


def configure_window(widget: QWidget) -> None:
    return None


def set_launch_at_login(enabled: bool) -> None:
    if enabled:
        LAUNCH_AGENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAUNCH_AGENT_FILE.write_text(_plist(), encoding="utf-8")
    elif LAUNCH_AGENT_FILE.exists():
        LAUNCH_AGENT_FILE.unlink()


def _plist() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        "    <string>com.izzet.quotabubble</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        "        <string>/bin/sh</string>\n"
        "        <string>-c</string>\n"
        f"        <string>{launch_command()}</string>\n"
        "    </array>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )
