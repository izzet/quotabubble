from __future__ import annotations

import logging
import os
import plistlib
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QWidget

from quotabubble.platform.launch import launch_arguments
from quotabubble.utils import write_text_atomic

LAUNCH_AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / "com.izzet.quotabubble.plist"
LAUNCH_AGENT_LABEL = "com.izzet.quotabubble"
logger = logging.getLogger(__name__)


def configure_window(widget: QWidget) -> None:
    return None


def set_launch_at_login(enabled: bool) -> None:
    service = _service_target()
    if not enabled:
        if _is_loaded(service):
            _run_launchctl("bootout", service)
        try:
            LAUNCH_AGENT_FILE.unlink()
        except FileNotFoundError:
            pass
        return

    plist = _plist()
    try:
        existing = LAUNCH_AGENT_FILE.read_text(encoding="utf-8")
    except OSError:
        existing = None
    if existing == plist and _is_loaded(service):
        return

    if _is_loaded(service):
        _run_launchctl("bootout", service)
    LAUNCH_AGENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(LAUNCH_AGENT_FILE, plist)
    _run_launchctl("bootstrap", service, str(LAUNCH_AGENT_FILE))


def _service_target() -> str:
    return f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"


def _is_loaded(service: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", service], capture_output=True, check=False, text=True
    )
    return result.returncode == 0


def _run_launchctl(*arguments: str) -> bool:
    result = subprocess.run(
        ["launchctl", *arguments], capture_output=True, check=False, text=True
    )
    if result.returncode != 0:
        logger.warning("launchctl %s failed: %s", arguments[0], result.stderr.strip())
        return False
    return True


def _plist() -> str:
    return plistlib.dumps(
        {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": launch_arguments(),
            "RunAtLoad": True,
        },
        fmt=plistlib.FMT_XML,
    ).decode("utf-8")
