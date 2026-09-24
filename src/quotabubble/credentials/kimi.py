from __future__ import annotations

import json
import os
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://api.kimi.com"
_PROVIDER_KEY = "managed:kimi-code"
_FRESHNESS_SKEW_SECONDS = 60.0


@dataclass(frozen=True)
class KimiCodeLogin:
    """The Kimi Code CLI's OAuth login. The CLI owns and refreshes it."""

    access_token: str
    refresh_token: str
    expires_at: float | None

    def is_fresh(self, now: float) -> bool:
        return (
            bool(self.access_token)
            and self.expires_at is not None
            and self.expires_at > now + _FRESHNESS_SKEW_SECONDS
        )


def kimi_code_home() -> Path:
    override = os.environ.get("KIMI_CODE_HOME", "").strip()
    return Path(override) if override else Path.home() / ".kimi-code"


def _config(home: Path) -> dict[str, object]:
    try:
        return tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _provider_config(home: Path) -> dict[str, object]:
    providers = _config(home).get("providers")
    provider = providers.get(_PROVIDER_KEY) if isinstance(providers, dict) else None
    return provider if isinstance(provider, dict) else {}


def _credential_candidates(home: Path) -> list[Path]:
    directory = home / "credentials"
    candidates: list[Path] = []
    oauth = _provider_config(home).get("oauth")
    key = oauth.get("key") if isinstance(oauth, dict) else None
    if isinstance(key, str) and key.strip():
        candidates.append(directory / f"{key.strip().rsplit('/', 1)[-1]}.json")
    candidates.append(directory / "kimi-code.json")
    try:
        others = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        others = []
    return [*candidates, *others]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_kimi_code_login() -> KimiCodeLogin | None:
    home = kimi_code_home()
    for path in _credential_candidates(home):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        access = raw.get("access_token")
        refresh = raw.get("refresh_token")
        access = access.strip() if isinstance(access, str) else ""
        refresh = refresh.strip() if isinstance(refresh, str) else ""
        if access or refresh:
            return KimiCodeLogin(access, refresh, _number(raw.get("expires_at")))
    return None


def _host_from_oauth_config(provider: dict[str, object]) -> str | None:
    oauth = provider.get("oauth")
    host = oauth.get("oauth_host") if isinstance(oauth, dict) else None
    hostname = urlparse(host).hostname if isinstance(host, str) else None
    if hostname and hostname.startswith("auth."):
        return f"https://api.{hostname.removeprefix('auth.')}"
    return None


def kimi_code_base_url() -> str | None:
    """The API host the Kimi Code CLI is configured for, or None if unknown.

    Kimi runs separate regional services (kimi.com and kimi.ai), so a CLI login is
    only ever sent to the host the CLI itself uses; there is deliberately no default.
    """
    override = os.environ.get("KIMI_CODE_BASE_URL", "").strip()
    if override:
        return override
    provider = _provider_config(kimi_code_home())
    configured = provider.get("base_url")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return _host_from_oauth_config(provider)


def kimi_code_device_id() -> str:
    """The CLI's device id, or a throwaway one; never writes into the CLI's directory."""
    try:
        existing = (kimi_code_home() / "device_id").read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    return existing or str(uuid.uuid4())
