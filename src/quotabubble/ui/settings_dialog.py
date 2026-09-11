from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
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

from quotabubble.app.settings import Settings
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
        self.refresh.setRange(10, 3600)
        self.refresh.setSingleStep(10)
        self.refresh.setSuffix(" s")
        self.refresh.setValue(max(10, settings.refresh_interval_ms // 1000))

        self.show_remaining = QCheckBox("Show percentage remaining")
        self.show_remaining.setChecked(settings.show_remaining)

        self.launch_at_login = QCheckBox("Launch at login")
        self.launch_at_login.setChecked(settings.launch_at_login)

        form = QFormLayout(self)
        form.addRow("Idle opacity", self.opacity)
        form.addRow("Fade delay", self.fade_delay)
        form.addRow("Refresh interval", self.refresh)
        form.addRow("", self.show_remaining)
        form.addRow("", self.launch_at_login)

        if self._providers:
            form.addRow(self._build_providers())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _build_providers(self) -> QGroupBox:
        group = QGroupBox("Providers")
        box = QVBoxLayout(group)
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
                field.setText(self._settings.api_keys.get(provider.id, ""))
                row.addWidget(field)

                button = QPushButton("Test")
                button.setEnabled(isinstance(provider, ApiKeyProvider))
                row.addWidget(button)

                status = QLabel("")
                status.setMinimumWidth(80)
                row.addWidget(status)

                field.textChanged.connect(lambda _text, lbl=status: lbl.setText(""))
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
        if self.provider_checks:
            enabled = [
                provider.id
                for provider, checkbox in self.provider_checks
                if checkbox.isChecked()
            ]
            for provider, field, _button, _status in self.provider_keys:
                value = field.text().strip()
                if value:
                    self._settings.api_keys[provider.id] = value
                    if provider.id not in enabled:
                        enabled.append(provider.id)
                else:
                    self._settings.api_keys.pop(provider.id, None)
            self._settings.enabled_providers = enabled
        self._settings.save(self._path)
        super().accept()
