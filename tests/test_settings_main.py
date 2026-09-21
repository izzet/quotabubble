from __future__ import annotations

import asyncio
import sys
from types import ModuleType

from PySide6.QtWidgets import QDialog

from quotabubble.app.settings import Settings


def test_notify_service_calls_reload_settings(monkeypatch) -> None:
    from quotabubble import settings_main

    calls: list[str] = []

    class Interface:
        async def call_reload_settings(self) -> None:
            calls.append("reload")

    class Bus:
        async def connect(self):
            return self

        async def introspect(self, name: str, path: str):
            calls.append(f"introspect:{name}:{path}")
            return object()

        def get_proxy_object(self, name: str, path: str, introspection: object):
            return self

        def get_interface(self, name: str) -> Interface:
            calls.append(f"interface:{name}")
            return Interface()

        def disconnect(self) -> None:
            calls.append("disconnect")

    aio = ModuleType("dbus_fast.aio")
    aio.MessageBus = Bus  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dbus_fast.aio", aio)

    asyncio.run(settings_main._notify_service())

    assert calls == [
        "introspect:dev.izzet.quotabubble:/dev/izzet/quotabubble",
        "interface:dev.izzet.quotabubble.Service1",
        "reload",
        "disconnect",
    ]


def test_settings_launcher_notifies_service_after_a_save(qapp: object, monkeypatch) -> None:
    from quotabubble import settings_main

    notified: list[bool] = []

    class Dialog:
        def __init__(self, settings: Settings, providers: list[object]) -> None:
            assert settings == Settings()
            assert providers == []

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    async def notify() -> None:
        notified.append(True)

    monkeypatch.setattr(settings_main, "QApplication", lambda argv: qapp)
    monkeypatch.setattr(settings_main, "SettingsDialog", Dialog)
    monkeypatch.setattr(settings_main.Settings, "load", lambda: Settings())
    monkeypatch.setattr(settings_main, "build_providers", lambda settings: [])
    monkeypatch.setattr(settings_main, "_notify_service", notify)
    monkeypatch.setattr(settings_main.sys, "platform", "linux")

    settings_main.main()

    assert notified == [True]
