from __future__ import annotations

import sys

import pytest

from quotabubble import platform as quotabubble_platform


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has a real implementation")
def test_packaging_is_never_detected_off_windows() -> None:
    assert quotabubble_platform.is_packaged() is False


def test_platform_exports_the_shared_api() -> None:
    assert {"configure_window", "is_packaged", "set_launch_at_login"} <= set(
        quotabubble_platform.__all__
    )
