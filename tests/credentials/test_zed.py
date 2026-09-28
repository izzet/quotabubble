from __future__ import annotations

import pytest

from quotabubble.credentials import zed
from quotabubble.credentials.zed import read_zed_credentials

BLOB = b'{"version":2,"id":"abc","token":"secret"}'


def _reader(result: tuple[str, bytes] | None):
    def read(target: str) -> tuple[str, bytes] | None:
        assert target == "zed:url=https://zed.dev"
        return result

    return read


def test_returns_user_id_and_token_blob(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zed, "read_generic_credential_with_username", _reader(("42", BLOB)))

    assert read_zed_credentials() == ("42", BLOB.decode())


def test_decodes_utf16_blobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        zed, "read_generic_credential_with_username", _reader(("42", "tok".encode("utf-16-le")))
    )

    assert read_zed_credentials() == ("42", "tok")


@pytest.mark.parametrize(
    "found",
    [None, ("", BLOB), ("42", b"   "), ("42", b"\xff\xfe\xfa"), ("42", b"a\x00b\x00\x00")],
)
def test_incomplete_or_undecodable_credentials_are_ignored(
    monkeypatch: pytest.MonkeyPatch, found: tuple[str, bytes] | None
) -> None:
    monkeypatch.setattr(zed, "read_generic_credential_with_username", _reader(found))

    assert read_zed_credentials() is None
