from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

def test_generic_credentials_interface() -> None:
    from quotabubble.credentials.os.windows import (
        enumerate_generic_credentials,
        read_generic_credential,
    )

    assert enumerate_generic_credentials("non_existent_quota_bubble_target_xyz_123") == []
    assert read_generic_credential("non_existent_quota_bubble_target_xyz_123") is None


def test_read_generic_credential_with_username_round_trips() -> None:
    import subprocess

    from quotabubble.credentials.os.windows import (
        read_generic_credential,
        read_generic_credential_with_username,
    )

    target = "quota_bubble_test_target_with_username"
    subprocess.run(
        ["cmdkey", f"/generic:{target}", "/user:test-user", "/pass:test-secret"],
        check=True,
        capture_output=True,
    )
    try:
        username, blob = read_generic_credential_with_username(target)
        assert username == "test-user"
        assert blob.decode("utf-16-le") == "test-secret"
        assert read_generic_credential(target) == blob
    finally:
        subprocess.run(["cmdkey", f"/delete:{target}"], capture_output=True)


def test_read_generic_credential_with_username_missing_target() -> None:
    from quotabubble.credentials.os.windows import read_generic_credential_with_username

    assert read_generic_credential_with_username("non_existent_quota_bubble_target_xyz_123") is None
