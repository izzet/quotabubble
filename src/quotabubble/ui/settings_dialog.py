from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quotabubble.app.settings import Settings
from quotabubble.providers.base import Provider


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

        form = QFormLayout(self)
        form.addRow("Idle opacity", self.opacity)
        form.addRow("Fade delay", self.fade_delay)
        form.addRow("Refresh interval", self.refresh)
        form.addRow("", self.show_remaining)

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
            if not detected:
                label = f"{label} (not detected)"
            checkbox = QCheckBox(label)
            if self._settings.enabled_providers is None:
                checkbox.setChecked(detected)
            else:
                checkbox.setChecked(provider.id in self._settings.enabled_providers)
            checkbox.setEnabled(detected)
            box.addWidget(checkbox)
            self.provider_checks.append((provider, checkbox))
        return group

    def accept(self) -> None:
        self._settings.idle_opacity = self.opacity.value() / 100
        self._settings.fade_delay_ms = self.fade_delay.value()
        self._settings.refresh_interval_ms = self.refresh.value() * 1000
        self._settings.show_remaining = self.show_remaining.isChecked()
        if self.provider_checks:
            self._settings.enabled_providers = [
                provider.id
                for provider, checkbox in self.provider_checks
                if checkbox.isChecked()
            ]
        self._settings.save(self._path)
        super().accept()
