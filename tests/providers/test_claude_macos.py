from __future__ import annotations

import sys
from pathlib import Path

import pytest

from quotabubble.providers.claude import ClaudeProvider, read_keychain_credentials

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def test_keychain_credentials_are_read() -> None:
    blob = (FIXTURES / "claude_credentials.json").read_bytes()

    credentials = read_keychain_credentials(
        lambda hint, **_: [(f"{hint}-example:account", blob)]
    )

    assert credentials is not None
    assert credentials.access_token == "test-token"
    assert credentials.subscription_type == "max"


def test_keychain_credentials_take_priority(tmp_path: Path) -> None:
    blob = (FIXTURES / "claude_credentials.json").read_bytes()
    provider = ClaudeProvider(
        credentials_path=tmp_path / "absent.json",
        keychain_credentials_provider=lambda _, **__: [("Claude Code-credentials", blob)],
    )

    assert provider.detect() is True


def test_detect_authorizes_once_then_fetch_uses_cached_keychain_credential(
    tmp_path: Path,
) -> None:
    blob = (FIXTURES / "claude_credentials.json").read_bytes()
    interactions = []

    def credentials(hint: str, *, allow_interaction: bool) -> list[tuple[str, bytes]]:
        interactions.append((hint, allow_interaction))
        return [(hint, blob)]

    provider = ClaudeProvider(
        credentials_path=tmp_path / "absent.json",
        keychain_credentials_provider=credentials,
    )

    assert provider.detect() is True
    assert provider._credentials() is not None
    assert interactions == [("Claude Code-credentials", True)]
