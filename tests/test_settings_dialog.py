from __future__ import annotations

from pathlib import Path

from quotabubble.app.settings import Settings
from quotabubble.providers.base import KeyStatus, UsageSnapshot
from quotabubble.ui.settings_dialog import SettingsDialog


class _FakeProvider:
    uses_api_key = False

    def __init__(self, provider_id: str, detected: bool) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()
        self._detected = detected

    def detect(self) -> bool:
        return self._detected

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


class _KeyProvider:
    id = "deepseek"
    display_name = "DeepSeek"
    uses_api_key = True

    def __init__(self, detected: bool) -> None:
        self._detected = detected

    def detect(self) -> bool:
        return self._detected

    def check_api_key(self, api_key: str) -> KeyStatus:
        return KeyStatus.VALID

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_key_provider_has_test_button(qapp: object, tmp_path: Path) -> None:
    dialog = SettingsDialog(
        Settings(), [_KeyProvider(False)], path=tmp_path / "settings.json"
    )

    _provider, _field, button, status = dialog.provider_keys[0]

    assert button.text() == "Test"
    assert button.isEnabled() is True
    assert status.text() == ""


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


def test_dialog_toggles_launch_at_login(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, path=tmp_path / "settings.json")

    dialog.launch_at_login.setChecked(True)
    dialog.accept()

    assert settings.launch_at_login is True


def test_dialog_lists_detected_providers(qapp: object, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings()
    providers = [_FakeProvider("claude", True), _FakeProvider("codex", False)]
    dialog = SettingsDialog(settings, providers, path=path)

    assert dialog.provider_checks[0][1].isChecked() is True
    assert dialog.provider_checks[1][1].isEnabled() is False

    dialog.provider_checks[0][1].setChecked(False)
    dialog.accept()

    assert settings.enabled_providers == []


def test_dialog_collects_api_keys(qapp: object, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings()
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=path)

    assert dialog.provider_checks[0][1].isEnabled() is True

    dialog.provider_keys[0][1].setText("secret-key")
    dialog.accept()

    assert settings.api_keys["deepseek"] == "secret-key"
    assert settings.enabled_providers == ["deepseek"]
