from __future__ import annotations

import logging
import plistlib
import subprocess
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


def test_enabling_replaces_loaded_agent(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "com.izzet.quotabubble.plist"
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "LAUNCH_AGENT_FILE", target)
    monkeypatch.setattr(macos, "_is_loaded", lambda service: True)
    monkeypatch.setattr(macos, "_run_launchctl", lambda *args: calls.append(args))

    macos.set_launch_at_login(True)

    assert calls == [
        ("bootout", macos._service_target()),
        ("bootstrap", macos._service_target(), str(target)),
    ]


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


def test_disabling_when_agent_file_is_missing_is_a_noop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(macos, "LAUNCH_AGENT_FILE", tmp_path / "missing.plist")
    monkeypatch.setattr(macos, "_is_loaded", lambda service: False)

    macos.set_launch_at_login(False)


def test_is_loaded_checks_launchctl_result(monkeypatch) -> None:
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode=0),
    )

    assert macos._is_loaded("gui/501/com.izzet.quotabubble") is True


def test_run_launchctl_reports_failures(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode=1, stderr="failed\n"),
    )

    with caplog.at_level(logging.WARNING):
        assert macos._run_launchctl("bootstrap", "gui/501/com.izzet.quotabubble") is False

    assert "launchctl bootstrap failed: failed" in caplog.text


def test_run_launchctl_reports_success(monkeypatch) -> None:
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode=0),
    )

    assert macos._run_launchctl("bootstrap", "gui/501/com.izzet.quotabubble") is True
