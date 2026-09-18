from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from quotabubble.utils import redact_secrets, strip_jsonc_comments, write_text_atomic


def test_strip_jsonc_comments_preserves_strings() -> None:
    text = """
    // Leading comment
    {
      /* block comment */
      "url": "https://opencode.ai/config.json", // inline comment
      "key": "val/*not a comment*/ue"
    }
    /* Trailing block comment */
    """
    cleaned = strip_jsonc_comments(text)
    data = json.loads(cleaned)
    assert data["url"] == "https://opencode.ai/config.json"
    assert data["key"] == "val/*not a comment*/ue"


def test_strip_jsonc_comments_escaped_quotes() -> None:
    text = '{"message": "Hello \\"//not a comment\\" world"}'
    cleaned = strip_jsonc_comments(text)
    data = json.loads(cleaned)
    assert data["message"] == 'Hello "//not a comment" world'


def test_strip_jsonc_comments_empty_and_no_comments() -> None:
    assert strip_jsonc_comments("") == ""
    assert strip_jsonc_comments('{"a": 1}') == '{"a": 1}'


def test_redact_secrets_authorization_header() -> None:
    text = 'headers: {"Authorization": "Bearer sk-abcdefghijklmnopqrstuvwx"}'
    redacted = redact_secrets(text)

    assert "sk-abcdefghijklmnopqrstuvwx" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_bearer_without_authorization_prefix() -> None:
    redacted = redact_secrets("token=Bearer abc123.def456-xyz")

    assert "abc123.def456-xyz" not in redacted


def test_redact_secrets_cookie_header() -> None:
    redacted = redact_secrets("Set-Cookie: session=abcdef0123456789; Path=/")

    assert "abcdef0123456789" not in redacted


def test_redact_secrets_api_key_assignment() -> None:
    redacted = redact_secrets("api_key=sk-or-v1-abcdefghijklmnopqrstuvwxyz")

    assert "sk-or-v1-abcdefghijklmnopqrstuvwxyz" not in redacted


def test_redact_secrets_bare_prefixed_key() -> None:
    redacted = redact_secrets("using key sk-abcdefghijklmnopqrstuvwx for the request")

    assert "sk-abcdefghijklmnopqrstuvwx" not in redacted


def test_redact_secrets_jwt() -> None:
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYwSNzoHtjxV"
    )
    redacted = redact_secrets(f"token: {jwt}")

    assert jwt not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_email_address() -> None:
    redacted = redact_secrets("logged in as jane.doe@example.com")

    assert "jane.doe@example.com" not in redacted


def test_redact_secrets_leaves_unrelated_text_alone() -> None:
    text = "provider 'claude' ok (2 windows)"

    assert redact_secrets(text) == text


def test_write_text_atomic_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "state.json"

    write_text_atomic(target, '{"a": 1}')

    assert target.read_text(encoding="utf-8") == '{"a": 1}'


def test_write_text_atomic_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"a": 1}', encoding="utf-8")

    write_text_atomic(target, '{"a": 2}')

    assert target.read_text(encoding="utf-8") == '{"a": 2}'


def test_write_text_atomic_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "state.json"

    write_text_atomic(target, "content")

    assert target.read_text(encoding="utf-8") == "content"


def test_write_text_atomic_leaves_original_intact_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"a": 1}', encoding="utf-8")

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError):
        write_text_atomic(target, '{"a": 2}')

    # The original file must be untouched, and no leftover temp file remains.
    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_write_text_atomic_surfaces_original_error_when_cleanup_also_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"a": 1}', encoding="utf-8")

    def _replace_boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    def _remove_boom(*args: object, **kwargs: object) -> None:
        raise OSError("temp file already gone")

    monkeypatch.setattr(os, "replace", _replace_boom)
    monkeypatch.setattr(os, "remove", _remove_boom)

    # The write failure must propagate, not the cleanup failure that follows it.
    with pytest.raises(OSError, match="disk full"):
        write_text_atomic(target, '{"a": 2}')

    assert target.read_text(encoding="utf-8") == '{"a": 1}'
