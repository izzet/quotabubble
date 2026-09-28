from __future__ import annotations

import logging
import sys

import keyring

if sys.platform == "linux":
    from quotabubble.credentials.os.linux import secret_service_needs_setup
else:

    def secret_service_needs_setup() -> bool:
        return False

logger = logging.getLogger(__name__)

SERVICE_NAME = "quotabubble"
_PROBE_KEY = "__quotabubble_probe__"


def get_secret(provider_id: str) -> str | None:
    try:
        if secret_service_needs_setup():
            return None
        return keyring.get_password(SERVICE_NAME, provider_id)
    except Exception:
        logger.warning("OS keyring unavailable while reading '%s'", provider_id)
        return None


def set_secret(provider_id: str, value: str) -> bool:
    try:
        if secret_service_needs_setup():
            return False
        keyring.set_password(SERVICE_NAME, provider_id, value)
        return True
    except Exception:
        logger.warning("OS keyring unavailable while writing '%s'", provider_id)
        return False


def delete_secret(provider_id: str) -> None:
    try:
        if secret_service_needs_setup():
            return
        keyring.delete_password(SERVICE_NAME, provider_id)
    except Exception:
        pass


def is_keyring_available() -> bool:
    try:
        if secret_service_needs_setup():
            return False
        keyring.get_password(SERVICE_NAME, _PROBE_KEY)
    except Exception:
        return False
    return True
