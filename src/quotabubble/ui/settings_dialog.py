from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSlider,
    QSpinBox,
    QWidget,
)

from quotabubble.app.settings import Settings


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        parent: QWidget | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._path = path
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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        self._settings.idle_opacity = self.opacity.value() / 100
        self._settings.fade_delay_ms = self.fade_delay.value()
        self._settings.refresh_interval_ms = self.refresh.value() * 1000
        self._settings.show_remaining = self.show_remaining.isChecked()
        self._settings.save(self._path)
        super().accept()
