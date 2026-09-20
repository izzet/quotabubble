from __future__ import annotations

import asyncio

from quotabubble.app.logging_setup import setup_logging
from quotabubble.app.settings import Settings
from quotabubble.service.dbus import DbusService
from quotabubble.service.runtime import ServiceRuntime


def main() -> None:
    setup_logging()
    runtime = ServiceRuntime(Settings.load())
    asyncio.run(DbusService(runtime).run())
