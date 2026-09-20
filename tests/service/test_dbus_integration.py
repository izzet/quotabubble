from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux D-Bus only")

_SESSION_BUS_PROBE = """
import asyncio

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType

from quotabubble.service.dbus import BUS_NAME, INTERFACE_NAME, OBJECT_PATH, DbusService


class Runtime:
    refresh_interval_seconds = 60.0

    def refresh(self, *, force: bool = False) -> None:
        pass

    def state_json(self) -> str:
        return '{"version":1,"snapshots":[]}'


async def check() -> None:
    service = DbusService(Runtime())
    await service.start()
    client = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        introspection = await client.introspect(BUS_NAME, OBJECT_PATH)
        proxy = client.get_proxy_object(BUS_NAME, OBJECT_PATH, introspection)
        state = await proxy.get_interface(INTERFACE_NAME).call_get_state()
        assert state == '{"version":1,"snapshots":[]}'
    finally:
        client.disconnect()
        service.close()


asyncio.run(check())
"""


def test_service_answers_a_session_bus_get_state_request() -> None:
    subprocess.run(
        ["dbus-run-session", "--", sys.executable, "-c", textwrap.dedent(_SESSION_BUS_PROBE)],
        check=True,
        capture_output=True,
        text=True,
    )
