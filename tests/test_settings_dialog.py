from __future__ import annotations

from pathlib import Path

from quotabubble.app.settings import Settings
from quotabubble.ui.settings_dialog import SettingsDialog


def test_dialog_applies_and_saves(qapp: object, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings()
    dialog = SettingsDialog(settings, path=path)

    dialog.opacity.setValue(25)
    dialog.fade_delay.setValue(1000)
    dialog.refresh.setValue(30)
    dialog.show_remaining.setChecked(True)
    dialog.accept()

    assert settings.idle_opacity == 0.25
    assert settings.fade_delay_ms == 1000
    assert settings.refresh_interval_ms == 30_000
    assert settings.show_remaining is True
    assert Settings.load(path).refresh_interval_ms == 30_000
