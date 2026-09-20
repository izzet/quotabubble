from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from quotabubble.platform import macos

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def test_enabling_launch_at_login_writes_and_bootstraps_agent(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "LaunchAgents" / "com.izzet.quotabubble.plist"
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "LAUNCH_AGENT_FILE", target)
    monkeypatch.setattr(macos, "_is_loaded", lambda service: False)
    monkeypatch.setattr(macos, "_run_launchctl", lambda *args: calls.append(args))

    macos.set_launch_at_login(True)

    payload = plistlib.loads(target.read_bytes())
    assert payload["Label"] == "com.izzet.quotabubble"
    assert payload["ProgramArguments"]
    assert payload["RunAtLoad"] is True
    assert calls == [("bootstrap", macos._service_target(), str(target))]


def test_configure_window_keeps_tool_visible_while_inactive(qapp: object) -> None:
    widget = QWidget()

    macos.configure_window(widget)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    widget.deleteLater()


def test_unchanged_loaded_agent_is_not_restarted(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "com.izzet.quotabubble.plist"
    target.write_text(macos._plist(), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "LAUNCH_AGENT_FILE", target)
    monkeypatch.setattr(macos, "_is_loaded", lambda service: True)
    monkeypatch.setattr(macos, "_run_launchctl", lambda *args: calls.append(args))

    macos.set_launch_at_login(True)

    assert calls == []


def test_disabling_launch_at_login_unloads_and_removes_agent(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "com.izzet.quotabubble.plist"
    target.write_text(macos._plist(), encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "LAUNCH_AGENT_FILE", target)
    monkeypatch.setattr(macos, "_is_loaded", lambda service: True)
    monkeypatch.setattr(macos, "_run_launchctl", lambda *args: calls.append(args))

    macos.set_launch_at_login(False)

    assert target.exists() is False
    assert calls == [("bootout", macos._service_target())]
