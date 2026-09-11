from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog

from quotabubble.app.polling import PollingService
from quotabubble.app.providers import build_providers, loading_snapshot, select_providers
from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.ui.bubble import BubbleWindow
from quotabubble.ui.icon import app_icon
from quotabubble.ui.settings_dialog import SettingsDialog
from quotabubble.ui.tray import TrayIcon


def main() -> None:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBubble")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    settings = Settings.load()

    state = AppState()
    window = BubbleWindow(state, settings)
    window.show()

    tray = TrayIcon(window)
    tray.show()

    services: list[PollingService] = []

    def start_service() -> None:
        providers = select_providers(build_providers(settings), settings)
        state.replace([loading_snapshot(provider) for provider in providers])
        window.refresh()
        service = PollingService(providers, settings.refresh_interval_ms)
        service.snapshot_ready.connect(window.apply_snapshot)
        service.start()
        services.append(service)

    def stop_service() -> None:
        while services:
            services.pop().stop()

    def open_settings() -> None:
        dialog = SettingsDialog(settings, build_providers(settings), window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_service()
            start_service()
            window.apply_settings()

    window.settings_requested.connect(open_settings)
    tray.settings_requested.connect(open_settings)
    app.aboutToQuit.connect(stop_service)

    start_service()
    sys.exit(app.exec())
