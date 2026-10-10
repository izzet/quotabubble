from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def test_generic_credentials_interface() -> None:
    from quotabubble.credentials.os.macos import (
        enumerate_generic_credentials,
        read_generic_credential,
    )

    assert enumerate_generic_credentials("non_existent_quota_bubble_target_xyz_123") == []
    assert read_generic_credential("non_existent_quota_bubble_target_xyz_123") is None


def test_generic_credential_queries_never_wait_for_keychain_ui(monkeypatch) -> None:
    from quotabubble.credentials.os import macos

    queries = []
    interactions = []

    def no_match(query, _result):
        queries.append(query)
        return -1, None

    monkeypatch.setattr(macos, "SecItemCopyMatching", no_match)
    monkeypatch.setattr(
        macos, "SecKeychainSetUserInteractionAllowed", interactions.append
    )

    assert macos.read_generic_credential("service:account") is None
    assert macos.enumerate_generic_credentials("claude") == []
    assert queries[1][macos.kSecAttrService] == "claude"
    assert interactions == [False, True, False, True]
    assert all(
        query[macos.kSecUseAuthenticationUI] == macos.kSecUseAuthenticationUIFail
        for query in queries
    )


def test_interactive_credential_query_allows_keychain_authorization(monkeypatch) -> None:
    from quotabubble.credentials.os import macos

    queries = []
    interactions = []

    def no_match(query, _result):
        queries.append(query)
        return -1, None

    monkeypatch.setattr(macos, "SecItemCopyMatching", no_match)
    monkeypatch.setattr(
        macos, "SecKeychainSetUserInteractionAllowed", interactions.append
    )

    assert macos._copy_data("Claude Code-credentials", allow_interaction=True) is None
    assert interactions == []
    assert queries[0][macos.kSecUseAuthenticationUI] == macos.kSecUseAuthenticationUIAllow
