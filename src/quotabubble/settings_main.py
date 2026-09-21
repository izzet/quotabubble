from __future__ import annotations

import asyncio
import sys

from PySide6.QtWidgets import QApplication, QDialog

from quotabubble.app.providers import build_providers
from quotabubble.app.settings import Settings
from quotabubble.platform import set_launch_at_login
from quotabubble.ui.icon import app_icon
from quotabubble.ui.settings_dialog import SettingsDialog


async def _call_service(method: str) -> None:
    from dbus_fast.aio import MessageBus

    bus = await MessageBus().connect()
    try:
        introspection = await bus.introspect(
            "dev.izzet.quotabubble", "/dev/izzet/quotabubble"
        )
        proxy = bus.get_proxy_object(
            "dev.izzet.quotabubble", "/dev/izzet/quotabubble", introspection
        )
        interface = proxy.get_interface("dev.izzet.quotabubble.Service1")
        await getattr(interface, f"call_{method}")()
    finally:
        bus.disconnect()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("QuotaBubble Settings")
    app.setWindowIcon(app_icon())
    settings = Settings.load()
    dialog = SettingsDialog(settings, build_providers(settings))
    dialog.test_notification_requested.connect(
        lambda: asyncio.run(_call_service("test_notification"))
    )
    if dialog.exec() == QDialog.DialogCode.Accepted and sys.platform == "linux":
        set_launch_at_login(settings.launch_at_login)
        asyncio.run(_call_service("reload_settings"))
