from __future__ import annotations

import pytest
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from quotabubble.app.instance import SingleInstance


def test_second_instance_cannot_acquire(qapp: object) -> None:
    name = "quotabubble-test-instance"
    first = SingleInstance(lambda: None, name=name)

    assert first.acquire() is True
    try:
        second = SingleInstance(lambda: None, name=name)
        assert second.acquire() is False
    finally:
        first.close()


def test_second_instance_triggers_on_activate_callback(qapp: object) -> None:
    name = "quotabubble-test-instance-activate"
    activated: list[bool] = []
    first = SingleInstance(lambda: activated.append(True), name=name)

    assert first.acquire() is True
    try:
        second = SingleInstance(lambda: None, name=name)
        assert second.acquire() is False

        # The newConnection signal on the first instance's server is
        # delivered asynchronously through the event loop.
        for _ in range(50):
            if activated:
                break
            QApplication.processEvents()

        assert activated == [True]
    finally:
        first.close()


def test_acquire_recovers_from_stale_lock(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a previous instance crashed and left a stale server registration,
    the OS-level bind fails but no live peer answers; acquire() should clean
    up the stale registration and retry successfully."""
    listen_calls: list[str] = []

    def fake_listen(self: QLocalServer, requested_name: str) -> bool:
        listen_calls.append(requested_name)
        return len(listen_calls) > 1

    removed: list[str] = []

    def fake_remove_server(requested_name: str) -> bool:
        removed.append(requested_name)
        return True

    monkeypatch.setattr(QLocalServer, "listen", fake_listen)
    monkeypatch.setattr(QLocalServer, "removeServer", staticmethod(fake_remove_server))

    instance = SingleInstance(lambda: None, name="quotabubble-test-stale-lock")
    notify_calls = iter([False, False])
    monkeypatch.setattr(instance, "_notify_existing", lambda: next(notify_calls))

    assert instance.acquire() is True
    assert listen_calls == ["quotabubble-test-stale-lock"] * 2
    assert removed == ["quotabubble-test-stale-lock"]


def test_acquire_loses_race_to_a_real_instance(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If listen() fails and a peer answers on the recheck, a real instance
    won the race while we were trying to bind; we must back off cleanly."""

    def fake_listen(self: QLocalServer, requested_name: str) -> bool:
        return False

    monkeypatch.setattr(QLocalServer, "listen", fake_listen)

    instance = SingleInstance(lambda: None, name="quotabubble-test-race-lost")
    notify_calls = iter([False, True])
    monkeypatch.setattr(instance, "_notify_existing", lambda: next(notify_calls))

    assert instance.acquire() is False
    assert instance._server is None


def test_acquire_gives_up_when_recovery_also_fails(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If listen() fails even after removing the stale registration, acquire()
    must give up rather than loop or raise."""

    def fake_listen(self: QLocalServer, requested_name: str) -> bool:
        return False

    monkeypatch.setattr(QLocalServer, "listen", fake_listen)
    monkeypatch.setattr(QLocalServer, "removeServer", staticmethod(lambda name: True))

    instance = SingleInstance(lambda: None, name="quotabubble-test-recovery-fails")
    monkeypatch.setattr(instance, "_notify_existing", lambda: False)

    assert instance.acquire() is False
    assert instance._server is None
