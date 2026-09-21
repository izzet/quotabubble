from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from quotabubble.credentials.os import read_generic_credential

_COPILOT_SERVICE = "copilot-cli"
_DEFAULT_HOST = "github.com"


def _config_path() -> Path:
    home = os.environ.get("COPILOT_HOME")
    return Path(home) / "config.json" if home else Path.home() / ".copilot" / "config.json"


def _last_logged_in_user() -> tuple[str, str] | None:
    try:
        raw = _config_path().read_text(encoding="utf-8")
        lines = (line for line in raw.splitlines() if not line.lstrip().startswith("//"))
        payload = json.loads("\n".join(lines))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    user = payload.get("lastLoggedInUser")
    if not isinstance(user, dict):
        return None
    host = user.get("host")
    login = user.get("login")
    if (
        not isinstance(host, str)
        or not host.strip()
        or not isinstance(login, str)
        or not login.strip()
    ):
        return None
    return host.strip(), login.strip()


def read_copilot_cli_credentials() -> list[tuple[str, bytes]]:
    """Read the active Copilot CLI OAuth token from the OS credential store."""
    if sys.platform != "linux":
        return []
    account = _last_logged_in_user()
    if account is None:
        return []
    host, login = account
    target = f"{_COPILOT_SERVICE}:https://{host or _DEFAULT_HOST}:{login}"
    token = read_generic_credential(target)
    return [(target, token)] if token is not None else []
