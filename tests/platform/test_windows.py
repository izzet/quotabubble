from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

APPMODEL_ERROR_NO_PACKAGE = 15700
ERROR_INSUFFICIENT_BUFFER = 122


class _FakeKernel32:
    def __init__(self, result: int) -> None:
        self._result = result

        class _Call:
            def __call__(inner, length, buffer) -> int:
                return self._result

        self.GetCurrentPackageFullName = _Call()


def test_an_unpackaged_process_is_not_packaged() -> None:
    from quotabubble.platform import windows

    assert windows.is_packaged() is False


@pytest.mark.parametrize(
    ("result", "expected"),
    [(APPMODEL_ERROR_NO_PACKAGE, False), (ERROR_INSUFFICIENT_BUFFER, True), (0, True)],
)
def test_packaged_means_the_process_has_package_identity(
    monkeypatch: pytest.MonkeyPatch, result: int, expected: bool
) -> None:
    from quotabubble.platform import windows

    monkeypatch.setattr(windows, "_kernel32", _FakeKernel32(result))

    assert windows.is_packaged() is expected


class _FakeKey:
    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_launch_at_login_writes_the_run_key_when_unpackaged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quotabubble.platform import windows

    written: list[tuple[str, str]] = []
    monkeypatch.setattr(windows, "is_packaged", lambda: False)
    monkeypatch.setattr(windows, "launch_command", lambda: "quotabubble.exe")
    monkeypatch.setattr(windows.winreg, "OpenKey", lambda *args: _FakeKey())
    monkeypatch.setattr(
        windows.winreg, "SetValueEx", lambda key, name, _r, _t, value: written.append((name, value))
    )

    windows.set_launch_at_login(True)

    assert written == [("QuotaBubble", "quotabubble.exe")]


def test_launch_at_login_removes_the_run_key_and_tolerates_a_missing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quotabubble.platform import windows

    deleted: list[str] = []

    def delete(key: object, name: str) -> None:
        deleted.append(name)
        raise FileNotFoundError

    monkeypatch.setattr(windows, "is_packaged", lambda: False)
    monkeypatch.setattr(windows.winreg, "OpenKey", lambda *args: _FakeKey())
    monkeypatch.setattr(windows.winreg, "DeleteValue", delete)

    windows.set_launch_at_login(False)

    assert deleted == ["QuotaBubble"]


@pytest.mark.parametrize("enabled", [True, False])
def test_launch_at_login_does_not_touch_the_registry_when_packaged(
    monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    from quotabubble.platform import windows

    def fail(*args: object) -> None:
        raise AssertionError("a packaged app must not write the Run key")

    monkeypatch.setattr(windows, "is_packaged", lambda: True)
    monkeypatch.setattr(windows.winreg, "OpenKey", fail)

    windows.set_launch_at_login(enabled)
