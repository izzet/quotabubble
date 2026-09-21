from __future__ import annotations

import asyncio
import sys

import pytest

if sys.platform != "linux":
    pytest.skip("D-Bus service is Linux only", allow_module_level=True)

from quotabubble.service.dbus import BUS_NAME, OBJECT_PATH, DbusService


class _Runtime:
    refresh_interval_seconds = 60.0

    def __init__(self) -> None:
        self.refreshes: list[bool] = []
        self.position: tuple[int, int] | None = None

    def refresh(self, *, force: bool = False) -> None:
        self.refreshes.append(force)

    def set_position(self, x: int, y: int) -> None:
        self.position = (x, y)

    def state_json(self) -> str:
        return '{"version":1,"snapshots":[]}'

    def appearance_json(self) -> str:
        return '{"idle_opacity":0.6}'

    def reload_settings(self) -> None:
        self.refreshes.append(False)

    def take_notifications(self) -> list[object]:
        return []


class _Bus:
    def __init__(self) -> None:
        self.exported: tuple[str, object] | None = None
        self.requested_name: str | None = None

    async def connect(self) -> _Bus:
        return self

    def export(self, path: str, interface: object) -> None:
        self.exported = (path, interface)

    async def request_name(self, name: str) -> None:
        self.requested_name = name

    def disconnect(self) -> None:
        pass


def test_service_exports_versioned_interface_and_current_state() -> None:
    runtime = _Runtime()
    bus = _Bus()
    service = DbusService(runtime, bus_factory=lambda: bus)  # type: ignore[arg-type]

    asyncio.run(service.start())

    assert bus.exported is not None
    assert bus.exported[0] == OBJECT_PATH
    assert bus.requested_name == BUS_NAME
    assert service._interface.GetState.__wrapped__(service._interface) == runtime.state_json()

    service.close()
    assert service._bus is None


def test_requested_refresh_runs_in_the_background() -> None:
    runtime = _Runtime()
    service = DbusService(runtime)

    async def request_and_wait() -> None:
        service.request_refresh()
        assert service._refresh_task is not None
        await service._refresh_task

    asyncio.run(request_and_wait())

    assert runtime.refreshes == [True]


def test_requested_settings_reload_refreshes_the_shared_state() -> None:
    runtime = _Runtime()
    service = DbusService(runtime)

    async def reload_and_wait() -> None:
        service.request_settings_reload()
        assert service._refresh_task is not None
        await service._refresh_task

    asyncio.run(reload_and_wait())

    assert runtime.refreshes == [False, True]


def test_interface_declares_appearance_signal() -> None:
    runtime = _Runtime()
    service = DbusService(runtime)

    assert service._interface.AppearanceChanged.__wrapped__(
        service._interface, '{"idle_opacity":0.6}'
    ) == '{"idle_opacity":0.6}'


def test_interface_declares_notification_signal() -> None:
    runtime = _Runtime()
    service = DbusService(runtime)

    assert service._interface.NotificationRaised.__wrapped__(
        service._interface, "QuotaBubble", "Quota warning", "critical"
    ) == ["QuotaBubble", "Quota warning", "critical"]


def test_interface_declares_set_position() -> None:
    runtime = _Runtime()
    service = DbusService(runtime)

    service._interface.SetPosition.__wrapped__(service._interface, 100, 200)
    assert runtime.position == (100, 200)
