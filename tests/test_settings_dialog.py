from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

from quotabubble.app.settings import Settings
from quotabubble.providers.base import KeyStatus, UsageSnapshot
from quotabubble.ui.settings_dialog import SettingsDialog


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A working in-memory keyring, wired into both the dialog (writes) and
    app.providers.resolve_api_key (reads, used for prefill)."""
    store: dict[str, str] = {}

    monkeypatch.setattr(
        "quotabubble.ui.settings_dialog.set_secret",
        lambda provider_id, value: store.__setitem__(provider_id, value) or True,
    )
    monkeypatch.setattr(
        "quotabubble.ui.settings_dialog.delete_secret",
        lambda provider_id: store.pop(provider_id, None),
    )
    monkeypatch.setattr("quotabubble.ui.settings_dialog.is_keyring_available", lambda: True)
    monkeypatch.setattr(
        "quotabubble.app.providers.get_secret", lambda provider_id: store.get(provider_id)
    )
    return store


@pytest.fixture
def broken_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quotabubble.ui.settings_dialog.set_secret", lambda provider_id, value: False
    )
    monkeypatch.setattr("quotabubble.ui.settings_dialog.delete_secret", lambda provider_id: None)
    monkeypatch.setattr("quotabubble.ui.settings_dialog.is_keyring_available", lambda: False)
    monkeypatch.setattr("quotabubble.app.providers.get_secret", lambda provider_id: None)


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


def test_key_provider_has_test_button(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
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
    dialog.refresh.setValue(300)
    dialog.show_remaining.setChecked(True)
    dialog.accept()

    assert settings.idle_opacity == 0.25
    assert settings.fade_delay_ms == 1000
    assert settings.refresh_interval_ms == 300_000
    assert settings.show_remaining is True
    assert Settings.load(path).refresh_interval_ms == 300_000


def test_dialog_toggles_launch_at_login(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, path=tmp_path / "settings.json")

    dialog.launch_at_login.setChecked(True)
    dialog.accept()

    assert settings.launch_at_login is True


def test_dialog_toggles_history_enabled(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, path=tmp_path / "settings.json")

    assert dialog.history_enabled.isChecked() is False

    dialog.history_enabled.setChecked(True)
    dialog.accept()

    assert settings.history_enabled is True
    assert Settings.load(tmp_path / "settings.json").history_enabled is True


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


def test_dialog_collects_api_keys(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    path = tmp_path / "settings.json"
    settings = Settings()
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=path)

    assert dialog.provider_checks[0][1].isEnabled() is True

    dialog.provider_keys[0][1].setText("secret-key")
    dialog.accept()

    # Stored via the keyring, not in the plaintext settings file.
    assert fake_keyring["deepseek"] == "secret-key"
    assert "deepseek" not in settings.api_keys
    assert settings.enabled_providers == ["deepseek"]


def test_entering_a_first_key_ticks_the_provider(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    dialog = SettingsDialog(Settings(), [_KeyProvider(False)], path=tmp_path / "settings.json")
    checkbox = dialog.provider_checks[0][1]
    assert checkbox.isChecked() is False

    dialog.provider_keys[0][1].setText("k")

    assert checkbox.isChecked() is True


def test_unticking_a_provider_with_a_key_is_respected_and_keeps_the_key(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")
    dialog.provider_keys[0][1].setText("secret-key")
    dialog.provider_checks[0][1].setChecked(False)

    dialog.accept()

    assert settings.enabled_providers == []
    assert fake_keyring["deepseek"] == "secret-key"


def test_a_saved_key_does_not_force_the_provider_on_when_reopened(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    fake_keyring["deepseek"] = "existing-key"
    settings = Settings(enabled_providers=[])
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")

    assert dialog.provider_checks[0][1].isChecked() is False
    dialog.accept()

    assert settings.enabled_providers == []
    assert fake_keyring["deepseek"] == "existing-key"


def test_ticking_a_provider_with_a_saved_key_enables_it(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    fake_keyring["deepseek"] = "existing-key"
    settings = Settings(enabled_providers=[])
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")
    dialog.provider_checks[0][1].setChecked(True)

    dialog.accept()

    assert settings.enabled_providers == ["deepseek"]


def test_only_the_first_key_entry_auto_ticks(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    dialog = SettingsDialog(Settings(), [_KeyProvider(False)], path=tmp_path / "settings.json")
    checkbox = dialog.provider_checks[0][1]
    field = dialog.provider_keys[0][1]

    field.setText("a")
    checkbox.setChecked(False)
    field.setText("ab")
    assert checkbox.isChecked() is False

    field.setText("")
    field.setText("new")
    assert checkbox.isChecked() is True


def test_editing_an_existing_key_never_auto_ticks(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    fake_keyring["deepseek"] = "existing-key"
    settings = Settings(enabled_providers=[])
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")

    dialog.provider_keys[0][1].setText("existing-key-2")

    assert dialog.provider_checks[0][1].isChecked() is False


def test_dialog_prefills_field_from_keyring(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    fake_keyring["deepseek"] = "existing-key"
    settings = Settings()

    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")

    _provider, field, _button, _status = dialog.provider_keys[0]
    assert field.text() == "existing-key"


def test_dialog_clearing_field_deletes_secret(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    fake_keyring["deepseek"] = "existing-key"
    settings = Settings()
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")

    dialog.provider_keys[0][1].setText("")
    dialog.accept()

    assert "deepseek" not in fake_keyring
    assert "deepseek" not in settings.api_keys


def test_dialog_falls_back_to_plaintext_when_keyring_unavailable(
    qapp: object, tmp_path: Path, broken_keyring: None
) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, [_KeyProvider(False)], path=tmp_path / "settings.json")

    dialog.provider_keys[0][1].setText("secret-key")
    dialog.accept()

    assert settings.api_keys["deepseek"] == "secret-key"


def test_dialog_shows_warning_when_keyring_unavailable(
    qapp: object, tmp_path: Path, broken_keyring: None
) -> None:
    dialog = SettingsDialog(
        Settings(), [_KeyProvider(False)], path=tmp_path / "settings.json"
    )

    labels = [
        label.text()
        for label in dialog.findChildren(QLabel)
        if "keyring unavailable" in label.text().lower()
    ]
    assert labels


def test_dialog_no_warning_when_keyring_available(
    qapp: object, tmp_path: Path, fake_keyring: dict[str, str]
) -> None:
    dialog = SettingsDialog(
        Settings(), [_KeyProvider(False)], path=tmp_path / "settings.json"
    )

    labels = [
        label.text()
        for label in dialog.findChildren(QLabel)
        if "keyring unavailable" in label.text().lower()
    ]
    assert not labels


def test_dialog_notification_settings(qapp: object, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings()
    dialog = SettingsDialog(settings, path=path)

    assert dialog.notify_usage.isChecked() is True
    assert dialog.notify_status.isChecked() is True
    assert dialog.thresholds_field.text() == "75, 90"
    assert dialog.thresholds_field.isEnabled() is True

    # Disable usage notifications -> disables thresholds field
    dialog.notify_usage.setChecked(False)
    assert dialog.thresholds_field.isEnabled() is False

    dialog.notify_status.setChecked(False)
    dialog.thresholds_field.setText("80, 95")
    dialog.accept()

    assert settings.notify_usage is False
    assert settings.notify_status is False
    assert settings.thresholds == [80, 95]


def test_dialog_test_notification_button(qapp: object, tmp_path: Path) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings, path=tmp_path / "settings.json")

    emitted = []
    dialog.test_notification_requested.connect(lambda: emitted.append(True))

    dialog.test_notification_btn.click()

    assert emitted == [True]
    assert dialog.test_notification_status.text() == "Sent!"
