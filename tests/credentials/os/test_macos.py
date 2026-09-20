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
