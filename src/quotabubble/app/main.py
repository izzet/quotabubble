from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog

from quotabubble.app.instance import SingleInstance
from quotabubble.app.polling import PollingService
from quotabubble.app.providers import build_providers, loading_snapshot, select_providers
from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.platform import set_launch_at_login
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
    set_launch_at_login(settings.launch_at_login)

    state = AppState()
    window = BubbleWindow(state, settings)

    instance = SingleInstance(window.show)
    if not instance.acquire():
        sys.exit(0)
    app.aboutToQuit.connect(instance.close)

    window.show()

    tray = TrayIcon(window)
    tray.show()

    providers = select_providers(build_providers(settings), settings)
    state.replace([loading_snapshot(provider) for provider in providers])
    window.refresh()

    service = PollingService(providers, settings.refresh_interval_ms)
    service.snapshot_ready.connect(window.apply_snapshot)
    service.start()

    def apply_providers() -> None:
        selected = select_providers(build_providers(settings), settings)
        state.replace([loading_snapshot(provider) for provider in selected])
        window.refresh()
        service.set_providers(selected)

    def open_settings() -> None:
        dialog = SettingsDialog(settings, build_providers(settings), window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            apply_providers()
            service.set_interval(settings.refresh_interval_ms)
            window.apply_settings()
            set_launch_at_login(settings.launch_at_login)

    window.settings_requested.connect(open_settings)
    tray.settings_requested.connect(open_settings)
    app.aboutToQuit.connect(service.stop)

    sys.exit(app.exec())
