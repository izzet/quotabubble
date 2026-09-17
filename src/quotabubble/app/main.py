from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog

from quotabubble.app.cache import load_snapshots
from quotabubble.app.instance import SingleInstance
from quotabubble.app.logging_setup import setup_logging
from quotabubble.app.notifications import NotificationManager
from quotabubble.app.polling import PollingService
from quotabubble.app.providers import build_providers, loading_snapshot, select_providers
from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.platform import set_launch_at_login
from quotabubble.ui.bubble import BubbleWindow
from quotabubble.ui.icon import app_icon
from quotabubble.ui.settings_dialog import SettingsDialog
from quotabubble.ui.tray import TrayIcon

logger = logging.getLogger(__name__)


def main() -> None:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBubble")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    setup_logging()
    logger.info("QuotaBubble starting")

    settings = Settings.load()
    set_launch_at_login(settings.launch_at_login)

    state = AppState()
    window = BubbleWindow(state, settings)

    def seed_state(selected: list) -> None:
        cached = load_snapshots()
        snapshots = []
        for provider in selected:
            previous = cached.get(provider.id)
            if previous is not None:
                snapshots.append(previous.model_copy(update={"stale": True}))
            else:
                snapshots.append(loading_snapshot(provider))
        state.replace(snapshots)
        window.refresh()

    instance = SingleInstance(window.show)
    if not instance.acquire():
        sys.exit(0)
    app.aboutToQuit.connect(instance.close)

    window.show()

    tray = TrayIcon(window)
    tray.show()

    notification_manager = NotificationManager(settings)
    notification_manager.notify.connect(tray.show_notification)

    providers = select_providers(build_providers(settings), settings)
    logger.info("providers: %s", [provider.id for provider in providers])
    seed_state(providers)

    service = PollingService(providers, settings.refresh_interval_ms)
    service.snapshot_ready.connect(window.apply_snapshot)
    service.snapshot_ready.connect(notification_manager.process_snapshot)
    service.start()

    def apply_providers() -> None:
        selected = select_providers(build_providers(settings), settings)
        seed_state(selected)
        service.set_providers(selected)

    def open_settings() -> None:
        dialog = SettingsDialog(settings, build_providers(settings), window)
        dialog.test_notification_requested.connect(
            notification_manager.send_test_notification
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("settings applied")
            notification_manager.set_settings(settings)
            apply_providers()
            service.set_interval(settings.refresh_interval_ms)
            window.apply_settings()
            set_launch_at_login(settings.launch_at_login)

    window.settings_requested.connect(open_settings)
    tray.settings_requested.connect(open_settings)
    window.refresh_requested.connect(service.poll)
    tray.refresh_requested.connect(service.poll)
    app.aboutToQuit.connect(service.stop)

    sys.exit(app.exec())
