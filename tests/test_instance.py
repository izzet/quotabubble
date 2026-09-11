from __future__ import annotations

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
