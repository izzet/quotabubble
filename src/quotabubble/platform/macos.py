from __future__ import annotations

import ctypes
import logging
import os
import plistlib
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from quotabubble.platform.launch import launch_arguments
from quotabubble.utils import write_text_atomic

LAUNCH_AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / "com.izzet.quotabubble.plist"
LAUNCH_AGENT_LABEL = "com.izzet.quotabubble"
logger = logging.getLogger(__name__)


def configure_application() -> None:
    """Hide source runs from the Dock, matching the bundled app's LSUIElement."""
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p

    send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        ("objc_msgSend", objc)
    )
    send_void_integer = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long
    )(("objc_msgSend", objc))
    application_class = objc.objc_getClass(b"NSApplication")
    shared_application = objc.sel_registerName(b"sharedApplication")
    set_activation_policy = objc.sel_registerName(b"setActivationPolicy:")
    application = send_id(application_class, shared_application)
    # NSApplicationActivationPolicyAccessory hides the Dock icon while
    # retaining the status item and floating tool window.
    send_void_integer(application, set_activation_policy, 1)


def configure_window(widget: QWidget) -> None:
    # Qt maps Qt.Tool to NSPanel. macOS hides these panels when their app loses
    # focus unless this attribute is set, even with WindowStaysOnTopHint.
    widget.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)


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
