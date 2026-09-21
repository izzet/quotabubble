from __future__ import annotations

from quotabubble.credentials.os import linux


def test_read_generic_credential_reads_a_secret_service_item(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def get_password(service: str, account: str) -> str:
        calls.append((service, account))
        return '{"token":"value"}'

    monkeypatch.setattr(linux.keyring, "get_password", get_password)

    assert linux.read_generic_credential("gemini:antigravity") == b'{"token":"value"}'
    assert calls == [("gemini", "antigravity")]


def test_read_generic_credential_handles_invalid_targets_and_keyring_errors(monkeypatch) -> None:
    def get_password(*_args: object) -> str:
        raise RuntimeError

    monkeypatch.setattr(linux.keyring, "get_password", get_password)

    assert linux.read_generic_credential("gemini") is None
    assert linux.read_generic_credential("gemini:antigravity") is None
