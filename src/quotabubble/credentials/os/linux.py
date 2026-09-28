from __future__ import annotations

from contextlib import closing

import keyring
import secretstorage
from keyring.backends.SecretService import Keyring as SecretServiceKeyring


def secret_service_needs_setup() -> bool:
    """Check for a missing default collection without creating one."""
    try:
        backend = keyring.get_keyring()
        if not isinstance(backend, SecretServiceKeyring) or hasattr(
            backend, "preferred_collection"
        ):
            return False
        with closing(secretstorage.dbus_init()) as connection:
            secretstorage.get_collection_by_alias(connection, "default")
    except secretstorage.exceptions.ItemNotFoundException:
        return True
    except Exception:
        # Let the ordinary keyring operation report an unavailable backend.
        return False
    return False


def read_generic_credential(target: str) -> bytes | None:
    """Read a service/account pair from the desktop Secret Service."""
    service, separator, account = target.partition(":")
    if not separator or not service or not account:
        return None
    try:
        if secret_service_needs_setup():
            return None
        value = keyring.get_password(service, account)
    except Exception:
        return None
    return value.encode("utf-8") if value is not None else None


def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    """Secret Service does not offer safe portable enumeration through keyring."""
    return []
