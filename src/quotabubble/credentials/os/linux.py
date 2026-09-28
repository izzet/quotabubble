from __future__ import annotations

import keyring


def read_generic_credential(target: str) -> bytes | None:
    """Read a service/account pair from the desktop Secret Service."""
    service, separator, account = target.partition(":")
    if not separator or not service or not account:
        return None
    try:
        value = keyring.get_password(service, account)
    except Exception:
        return None
    return value.encode("utf-8") if value is not None else None


def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    """Secret Service does not offer safe portable enumeration through keyring."""
    return []
