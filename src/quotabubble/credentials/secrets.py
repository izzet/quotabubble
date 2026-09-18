from __future__ import annotations

import logging

import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "quotabubble"
_PROBE_KEY = "__quotabubble_probe__"


def get_secret(provider_id: str) -> str | None:
    try:
        return keyring.get_password(SERVICE_NAME, provider_id)
    except Exception:
        logger.warning("OS keyring unavailable while reading '%s'", provider_id)
        return None


def set_secret(provider_id: str, value: str) -> bool:
    try:
        keyring.set_password(SERVICE_NAME, provider_id, value)
        return True
    except Exception:
        logger.warning("OS keyring unavailable while writing '%s'", provider_id)
        return False


def delete_secret(provider_id: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, provider_id)
    except Exception:
        pass


def keyring_available() -> bool:
    try:
        keyring.get_password(SERVICE_NAME, _PROBE_KEY)
    except Exception:
        return False
    return True
