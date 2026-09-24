from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.credentials.os.windows import (
        enumerate_generic_credentials,
        read_generic_credential,
        read_generic_credential_with_username,
    )
elif sys.platform == "darwin":
    from quotabubble.credentials.os.macos import (
        enumerate_generic_credentials,
        read_generic_credential,
    )
elif sys.platform == "linux":
    from quotabubble.credentials.os.linux import (
        enumerate_generic_credentials,
        read_generic_credential,
    )
else:

    def read_generic_credential(target: str) -> bytes | None:
        return None

    def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
        return []


if sys.platform != "win32":

    def read_generic_credential_with_username(target: str) -> tuple[str, bytes] | None:
        return None


__all__ = [
    "enumerate_generic_credentials",
    "read_generic_credential",
    "read_generic_credential_with_username",
]
