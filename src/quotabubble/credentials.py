from __future__ import annotations

import sys

if sys.platform == "win32":
    from quotabubble.credentials_windows import read_generic_credential
else:

    def read_generic_credential(target: str) -> bytes | None:
        return None


__all__ = ["read_generic_credential"]
