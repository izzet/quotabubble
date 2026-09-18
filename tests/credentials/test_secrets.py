from __future__ import annotations

import pytest

from quotabubble.credentials import secrets


class _FakeKeyring:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        key = (service, username)
        if key not in self._store:
            raise RuntimeError("not found")
        del self._store[key]


class _UnavailableKeyring:
    def get_password(self, service: str, username: str) -> str | None:
        raise RuntimeError("no backend configured")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise RuntimeError("no backend configured")

    def delete_password(self, service: str, username: str) -> None:
        raise RuntimeError("no backend configured")


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> _FakeKeyring:
    fake = _FakeKeyring()
    monkeypatch.setattr(secrets, "keyring", fake)
    return fake


@pytest.fixture
def unavailable_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "keyring", _UnavailableKeyring())


def test_set_and_get_secret_roundtrip(fake_keyring: _FakeKeyring) -> None:
    assert secrets.set_secret("deepseek", "abc123") is True
    assert secrets.get_secret("deepseek") == "abc123"


def test_get_secret_missing_returns_none(fake_keyring: _FakeKeyring) -> None:
    assert secrets.get_secret("deepseek") is None


def test_delete_secret_removes_value(fake_keyring: _FakeKeyring) -> None:
    secrets.set_secret("deepseek", "abc123")

    secrets.delete_secret("deepseek")

    assert secrets.get_secret("deepseek") is None


def test_delete_secret_swallows_missing_entry(fake_keyring: _FakeKeyring) -> None:
    secrets.delete_secret("deepseek")  # no prior value; must not raise


def test_get_secret_returns_none_when_backend_unavailable(
    unavailable_keyring: None,
) -> None:
    assert secrets.get_secret("deepseek") is None


def test_set_secret_returns_false_when_backend_unavailable(
    unavailable_keyring: None,
) -> None:
    assert secrets.set_secret("deepseek", "abc123") is False


def test_delete_secret_swallows_backend_errors(unavailable_keyring: None) -> None:
    secrets.delete_secret("deepseek")  # must not raise


def test_keyring_available_true_with_working_backend(fake_keyring: _FakeKeyring) -> None:
    assert secrets.keyring_available() is True


def test_keyring_available_false_with_broken_backend(unavailable_keyring: None) -> None:
    assert secrets.keyring_available() is False
