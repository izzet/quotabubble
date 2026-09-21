from __future__ import annotations

import asyncio

from quotabubble.app.logging_setup import setup_logging
from quotabubble.app.settings import Settings
from quotabubble.service.runtime import ServiceRuntime


def _run_service(runtime: ServiceRuntime) -> None:
    from quotabubble.service.dbus import DbusService

    asyncio.run(DbusService(runtime).run())


def main() -> None:
    setup_logging()
    runtime = ServiceRuntime(Settings.load())
    _run_service(runtime)
