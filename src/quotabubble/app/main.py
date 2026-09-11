from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from quotabubble.app.polling import PollingService
from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.providers.base import ProviderStatus, UsageSnapshot
from quotabubble.providers.claude import ClaudeProvider
from quotabubble.providers.codex import CodexProvider
from quotabubble.ui.bubble import BubbleWindow
from quotabubble.ui.icon import app_icon
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
    providers = [ClaudeProvider(), CodexProvider()]

    state = AppState()
    for provider in providers:
        state.update(
            UsageSnapshot(
                provider=provider.id,
                display_name=provider.display_name,
                status=ProviderStatus.LOADING,
            )
        )

    window = BubbleWindow(state, settings)
    window.show()

    service = PollingService(providers, settings.refresh_interval_ms)
    service.snapshot_ready.connect(window.apply_snapshot)
    service.start()
    app.aboutToQuit.connect(service.stop)

    tray = TrayIcon(window)
    tray.show()

    sys.exit(app.exec())
