from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quotabubble.app.providers import resolve_api_key
from quotabubble.app.settings import Settings, format_thresholds, parse_thresholds
from quotabubble.credentials import delete_secret, is_keyring_available, set_secret
from quotabubble.providers.base import ApiKeyProvider, KeyStatus, Provider

_STATUS_STYLES = {
    KeyStatus.VALID: ("Valid", "#5ec584"),
    KeyStatus.INVALID: ("Invalid", "#e85c54"),
    KeyStatus.UNREACHABLE: ("Unreachable", "#9a9aa5"),
    KeyStatus.MISSING: ("Enter a key", "#9a9aa5"),
}


class _CheckSignals(QObject):
    finished = Signal(str, object)


class _KeyCheckTask(QRunnable):
    def __init__(self, provider: ApiKeyProvider, api_key: str, signals: _CheckSignals) -> None:
        super().__init__()
        self._provider = provider
        self._api_key = api_key
        self._signals = signals

    def run(self) -> None:
        try:
            status = self._provider.check_api_key(self._api_key)
        except Exception:
            status = KeyStatus.UNREACHABLE
        self._signals.finished.emit(self._provider.id, status)


class SettingsDialog(QDialog):
    test_notification_requested = Signal()

    def __init__(
        self,
        settings: Settings,
        providers: list[Provider] | None = None,
        parent: QWidget | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._path = path
        self._providers = providers or []
        self.provider_checks: list[tuple[Provider, QCheckBox]] = []
        self.provider_keys: list[tuple[Provider, QLineEdit, QPushButton, QLabel]] = []
        self._check_signals = _CheckSignals(self)
        self._check_signals.finished.connect(self._on_check_finished)
        self._tasks: dict[str, _KeyCheckTask] = {}

        self.setWindowTitle("QuotaBubble Settings")

        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(5, 100)
        self.opacity.setValue(round(settings.idle_opacity * 100))

        self.fade_delay = QSpinBox()
        self.fade_delay.setRange(0, 10_000)
        self.fade_delay.setSingleStep(100)
        self.fade_delay.setSuffix(" ms")
        self.fade_delay.setValue(settings.fade_delay_ms)

        self.refresh = QSpinBox()
        self.refresh.setRange(60, 3600)
        self.refresh.setSingleStep(30)
        self.refresh.setSuffix(" s")
        self.refresh.setValue(max(60, settings.refresh_interval_ms // 1000))

        self.show_remaining = QCheckBox("Show percentage remaining")
        self.show_remaining.setChecked(settings.show_remaining)

        self.launch_at_login = QCheckBox("Launch at login")
        self.launch_at_login.setChecked(settings.launch_at_login)

        self.history_enabled = QCheckBox("Collect local usage history (for future trends)")
        self.history_enabled.setChecked(settings.history_enabled)

        form = QFormLayout(self)
        form.addRow("Idle opacity", self.opacity)
        form.addRow("Fade delay", self.fade_delay)
        form.addRow("Refresh interval", self.refresh)
        form.addRow("", self.show_remaining)
        form.addRow("", self.launch_at_login)
        form.addRow("", self.history_enabled)
        form.addRow(self._build_notifications())

        if self._providers:
            form.addRow(self._build_providers())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _build_notifications(self) -> QGroupBox:
        group = QGroupBox("Notifications")
        box = QVBoxLayout(group)

        self.notify_usage = QCheckBox("Usage threshold alerts")
        self.notify_usage.setChecked(self._settings.notify_usage)
        box.addWidget(self.notify_usage)

        thresh_row = QHBoxLayout()
        thresh_label = QLabel("Alert thresholds (%):")
        self.thresholds_field = QLineEdit()
        self.thresholds_field.setPlaceholderText("e.g. 75, 90")
        self.thresholds_field.setText(format_thresholds(self._settings.thresholds))
        self.thresholds_field.setEnabled(self._settings.notify_usage)
        self.notify_usage.toggled.connect(self.thresholds_field.setEnabled)
        thresh_row.addWidget(thresh_label)
        thresh_row.addWidget(self.thresholds_field)
        box.addLayout(thresh_row)

        self.notify_status = QCheckBox("Depletion and recovery alerts")
        self.notify_status.setChecked(self._settings.notify_status)
        box.addWidget(self.notify_status)

        test_row = QHBoxLayout()
        self.test_notification_btn = QPushButton("Test notification")
        self.test_notification_btn.clicked.connect(self._on_test_notification_clicked)
        self.test_notification_status = QLabel("")
        self.test_notification_status.setStyleSheet("color: #5ec584")
        test_row.addWidget(self.test_notification_btn)
        test_row.addWidget(self.test_notification_status)
        test_row.addStretch()
        box.addLayout(test_row)

        return group

    def _on_test_notification_clicked(self) -> None:
        self.test_notification_requested.emit()
        self.test_notification_status.setText("Sent!")
        QTimer.singleShot(3000, lambda: self.test_notification_status.setText(""))

    def _build_providers(self) -> QGroupBox:
        group = QGroupBox("Providers")
        box = QVBoxLayout(group)
        needs_key_storage = any(provider.uses_api_key for provider in self._providers)
        if needs_key_storage and not is_keyring_available():
            warning = QLabel(
                "OS keyring unavailable — API keys will be stored in settings.json instead."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #e8b34c")
            box.addWidget(warning)
        for provider in self._providers:
            detected = provider.detect()
            label = provider.display_name
            if not provider.uses_api_key and not detected:
                label = f"{label} (not detected)"

            checkbox = QCheckBox(label)
            if self._settings.enabled_providers is None:
                checkbox.setChecked(detected)
            else:
                checkbox.setChecked(provider.id in self._settings.enabled_providers)
            checkbox.setEnabled(provider.uses_api_key or detected)

            row = QHBoxLayout()
            row.addWidget(checkbox)
            if provider.uses_api_key:
                field = QLineEdit()
                field.setEchoMode(QLineEdit.EchoMode.Password)
                field.setPlaceholderText("API key")
                field.setText(resolve_api_key(self._settings, provider.id) or "")
                row.addWidget(field)

                button = QPushButton("Test")
                button.setEnabled(isinstance(provider, ApiKeyProvider))
                row.addWidget(button)

                status = QLabel("")
                status.setMinimumWidth(80)
                row.addWidget(status)

                field.textChanged.connect(lambda _text, lbl=status: lbl.setText(""))
                self._enable_on_first_key(field, checkbox)
                button.clicked.connect(
                    lambda _checked=False, p=provider, f=field, b=button, s=status: (
                        self._start_check(p, f, b, s)
                    )
                )
                self.provider_keys.append((provider, field, button, status))
            row.addStretch()
            box.addLayout(row)
            self.provider_checks.append((provider, checkbox))
        return group

    @staticmethod
    def _enable_on_first_key(field: QLineEdit, checkbox: QCheckBox) -> None:
        """Tick the provider when a key is entered where there was none.

        Only that empty-to-filled transition ticks it; after that the checkbox is the
        user's to control, and an existing key never forces a provider on.
        """
        had_key = [bool(field.text().strip())]

        def on_text_changed(text: str) -> None:
            has_key = bool(text.strip())
            if has_key and not had_key[0]:
                checkbox.setChecked(True)
            had_key[0] = has_key

        field.textChanged.connect(on_text_changed)

    def _start_check(
        self,
        provider: Provider,
        field: QLineEdit,
        button: QPushButton,
        status: QLabel,
    ) -> None:
        api_key = field.text().strip()
        if not api_key:
            self._set_status(status, KeyStatus.MISSING)
            return
        if not isinstance(provider, ApiKeyProvider):
            return
        status.setText("Checking…")
        status.setStyleSheet("color: #9a9aa5")
        button.setEnabled(False)
        task = _KeyCheckTask(provider, api_key, self._check_signals)
        self._tasks[provider.id] = task
        QThreadPool.globalInstance().start(task)

    def _on_check_finished(self, provider_id: str, status: object) -> None:
        self._tasks.pop(provider_id, None)
        for provider, _field, button, label in self.provider_keys:
            if provider.id == provider_id:
                self._set_status(label, status)
                button.setEnabled(True)
                return

    @staticmethod
    def _set_status(label: QLabel, status: object) -> None:
        text, color = _STATUS_STYLES.get(status, ("", "#9a9aa5"))
        label.setText(text)
        label.setStyleSheet(f"color: {color}")

    def accept(self) -> None:
        self._settings.idle_opacity = self.opacity.value() / 100
        self._settings.fade_delay_ms = self.fade_delay.value()
        self._settings.refresh_interval_ms = self.refresh.value() * 1000
        self._settings.show_remaining = self.show_remaining.isChecked()
        self._settings.launch_at_login = self.launch_at_login.isChecked()
        self._settings.history_enabled = self.history_enabled.isChecked()
        self._settings.notify_usage = self.notify_usage.isChecked()
        self._settings.notify_status = self.notify_status.isChecked()
        thresh_text = self.thresholds_field.text().strip()
        if thresh_text:
            try:
                self._settings.thresholds = parse_thresholds(thresh_text)
            except ValueError:
                pass
        else:
            self._settings.thresholds = []
        if self.provider_checks:
            enabled = [
                provider.id
                for provider, checkbox in self.provider_checks
                if checkbox.isChecked()
            ]
            for provider, field, _button, _status in self.provider_keys:
                value = field.text().strip()
                if value:
                    if set_secret(provider.id, value):
                        self._settings.api_keys.pop(provider.id, None)
                    else:
                        self._settings.api_keys[provider.id] = value
                else:
                    delete_secret(provider.id)
                    self._settings.api_keys.pop(provider.id, None)
            self._settings.enabled_providers = enabled
        self._settings.save(self._path)
        super().accept()
