from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.credentials.os.windows import (
        enumerate_generic_credentials,
        read_generic_credential,
    )
elif sys.platform == "darwin":
    from quotabubble.credentials.os.macos import (
        enumerate_generic_credentials,
        read_generic_credential,
    )
else:

    def read_generic_credential(target: str) -> bytes | None:
        return None

    def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
        return []


__all__ = ["enumerate_generic_credentials", "read_generic_credential"]
