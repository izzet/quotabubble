from __future__ import annotations

from keyring.backends.SecretService import Keyring as SecretServiceKeyring
from secretstorage.exceptions import ItemNotFoundException

from quotabubble.credentials.os import linux


class _Connection:
    def close(self) -> None:
        pass


def test_missing_default_collection_is_detected_without_creating_one(monkeypatch) -> None:
    connection = _Connection()
    monkeypatch.setattr(linux.keyring, "get_keyring", SecretServiceKeyring)
    monkeypatch.setattr(linux.secretstorage, "dbus_init", lambda: connection)

    def missing(_connection: object, alias: str) -> None:
        assert _connection is connection
        assert alias == "default"
        raise ItemNotFoundException("no default collection")

    monkeypatch.setattr(linux.secretstorage, "get_collection_by_alias", missing)
    monkeypatch.setattr(
        linux.secretstorage,
        "get_default_collection",
        lambda _connection: (_ for _ in ()).throw(AssertionError("created a collection")),
    )

    assert linux.secret_service_needs_setup() is True


def test_existing_default_collection_allows_keyring(monkeypatch) -> None:
    monkeypatch.setattr(linux.keyring, "get_keyring", SecretServiceKeyring)
    monkeypatch.setattr(linux.secretstorage, "dbus_init", _Connection)
    monkeypatch.setattr(
        linux.secretstorage, "get_collection_by_alias", lambda _connection, _alias: object()
    )

    assert linux.secret_service_needs_setup() is False


def test_read_generic_credential_reads_a_secret_service_item(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def get_password(service: str, account: str) -> str:
        calls.append((service, account))
        return '{"token":"value"}'

    monkeypatch.setattr(linux.keyring, "get_password", get_password)
    monkeypatch.setattr(linux, "secret_service_needs_setup", lambda: False)

    assert linux.read_generic_credential("gemini:antigravity") == b'{"token":"value"}'
    assert calls == [("gemini", "antigravity")]


def test_read_generic_credential_handles_invalid_targets_and_keyring_errors(monkeypatch) -> None:
    def get_password(*_args: object) -> str:
        raise RuntimeError

    monkeypatch.setattr(linux.keyring, "get_password", get_password)
    monkeypatch.setattr(linux, "secret_service_needs_setup", lambda: False)

    assert linux.read_generic_credential("gemini") is None
    assert linux.read_generic_credential("gemini:antigravity") is None


def test_read_generic_credential_skips_keyring_when_no_default_collection(monkeypatch) -> None:
    missing = [True]
    monkeypatch.setattr(linux, "secret_service_needs_setup", lambda: missing[0])
    monkeypatch.setattr(
        linux.keyring,
        "get_password",
        lambda *_args: "available-after-setup",
    )

    assert linux.read_generic_credential("gemini:antigravity") is None
    missing[0] = False
    assert linux.read_generic_credential("gemini:antigravity") == b"available-after-setup"
