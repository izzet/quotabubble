from __future__ import annotations

from quotabubble.credentials.os import read_generic_credential_with_username

_ZED_TARGET = "zed:url=https://zed.dev"


def _decode(blob: bytes) -> str | None:
    """Zed stores the token as UTF-8; tolerate UTF-16 from other credential writers."""
    for encoding in ("utf-8", "utf-16-le"):
        try:
            text = blob.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" not in text:
            return text.strip() or None
    return None


def read_zed_credentials() -> tuple[str, str] | None:
    """Return Zed's (user id, access token) from the OS credential store.

    Only Windows Credential Manager is supported so far.
    """
    found = read_generic_credential_with_username(_ZED_TARGET)
    if found is None:
        return None
    user_id, blob = found
    token = _decode(blob)
    if not user_id or token is None:
        return None
    return user_id, token
