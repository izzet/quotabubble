from __future__ import annotations

import sys

from quotabubble.credentials.os import (
    enumerate_generic_credentials,
    read_generic_credential,
)

if sys.platform == "win32":
    from quotabubble.credentials.os import windows as win_creds


def test_generic_credentials_interface() -> None:
    creds = enumerate_generic_credentials("non_existent_quota_bubble_target_xyz_123")
    assert isinstance(creds, list)
    assert len(creds) == 0

    val = read_generic_credential("non_existent_quota_bubble_target_xyz_123")
    assert val is None


def test_windows_module_exports_on_win32() -> None:
    if sys.platform == "win32":
        assert win_creds.CRED_TYPE_GENERIC == 1
        assert callable(win_creds.enumerate_generic_credentials)
        assert callable(win_creds.read_generic_credential)
