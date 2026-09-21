from __future__ import annotations

import sys
from pathlib import Path

import pytest

from quotabubble.platform import linux

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux only")


def test_enabling_launch_at_login_writes_desktop_entry(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "autostart" / "quotabubble.desktop"
    monkeypatch.setattr(linux, "AUTOSTART_FILE", target)
    linux.set_launch_at_login(True)

    assert target.read_text(encoding="utf-8") == (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=QuotaBubble\n"
        "Exec=quotabubble-service\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def test_disabling_launch_at_login_removes_desktop_entry(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "autostart" / "quotabubble.desktop"
    target.parent.mkdir()
    target.write_text("old entry", encoding="utf-8")
    monkeypatch.setattr(linux, "AUTOSTART_FILE", target)

    linux.set_launch_at_login(False)

    assert target.exists() is False


def test_disabling_without_desktop_entry_is_a_noop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(linux, "AUTOSTART_FILE", tmp_path / "missing.desktop")

    linux.set_launch_at_login(False)
