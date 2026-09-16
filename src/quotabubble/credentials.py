from __future__ import annotations

import sys

from quotabubble.credentials_cursor import (
    default_cursor_db_path,
    read_cursor_access_token,
    resolve_cursor_session_token,
    session_cookie_from_access_token,
)

if sys.platform == "win32":
    from quotabubble.credentials_windows import (
        enumerate_generic_credentials,
        read_generic_credential,
    )
else:

    def read_generic_credential(target: str) -> bytes | None:
        return None

    def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
        return []


__all__ = [
    "default_cursor_db_path",
    "enumerate_generic_credentials",
    "read_cursor_access_token",
    "read_generic_credential",
    "resolve_cursor_session_token",
    "session_cookie_from_access_token",
]
