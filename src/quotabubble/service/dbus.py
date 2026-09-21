# ruff: noqa: F821, UP037

import asyncio
from collections.abc import Callable

from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, signal

from quotabubble.service.runtime import ServiceRuntime

BUS_NAME = "dev.izzet.quotabubble"
OBJECT_PATH = "/dev/izzet/quotabubble"
INTERFACE_NAME = "dev.izzet.quotabubble.Service1"


class QuotaBubbleInterface(ServiceInterface):
    def __init__(self, service: "DbusService") -> None:
        super().__init__(INTERFACE_NAME)
        self._service = service

    @method()
    def GetState(self) -> "s":
        return self._service.runtime.state_json()

    @method()
    def Refresh(self):
        self._service.request_refresh()

    @method()
    def ReloadSettings(self):
        self._service.request_settings_reload()

    @signal()
    def StateChanged(self, state: "s") -> "s":
        return state

    @signal()
    def NotificationRaised(self, title: "s", message: "s", urgency: "s") -> "sss":
        return [title, message, urgency]


class DbusService:
    def __init__(
        self,
        runtime: ServiceRuntime,
        *,
        bus_factory: Callable[[], MessageBus] = MessageBus,
    ) -> None:
        self.runtime = runtime
        self._bus_factory = bus_factory
        self._bus: MessageBus | None = None
        self._interface = QuotaBubbleInterface(self)
        self._refresh_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._bus = await self._bus_factory().connect()
        self._bus.export(OBJECT_PATH, self._interface)
        await self._bus.request_name(BUS_NAME)

    async def run(self) -> None:
        try:
            await self.start()
            await self.refresh()
            while True:
                await asyncio.sleep(self.runtime.refresh_interval_seconds)
                await self.refresh()
        finally:
            self.close()

    def close(self) -> None:
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None

    def request_refresh(self) -> None:
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self.refresh())

    def request_settings_reload(self) -> None:
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self.reload_settings())

    async def refresh(self) -> None:
        await asyncio.to_thread(self.runtime.refresh, force=True)
        self._interface.StateChanged(self.runtime.state_json())
        for event in self.runtime.take_notifications():
            self._interface.NotificationRaised(event.title, event.message, event.urgency)

    async def reload_settings(self) -> None:
        await asyncio.to_thread(self.runtime.reload_settings)
        await self.refresh()
