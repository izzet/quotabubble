from __future__ import annotations

import socket
import sys
import time
from collections.abc import Callable
from datetime import datetime
from importlib import metadata

import httpx2

from quotabubble.credentials.kimi import (
    DEFAULT_BASE_URL,
    KimiCodeLogin,
    kimi_code_base_url,
    kimi_code_device_id,
    read_kimi_code_login,
)
from quotabubble.providers.base import (
    KeyStatus,
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    as_number,
    format_plan,
    parse_timestamp,
)

REQUEST_TIMEOUT_SECONDS = 15.0
_MINUTES_PER_UNIT = {"TIME_UNIT_MINUTE": 1, "TIME_UNIT_HOUR": 60, "TIME_UNIT_DAY": 1440}
_RESET_KEYS = ("resetTime", "resetAt", "reset_time", "reset_at")
_PLAN_NAMES = {
    "FREE": "Adagio",
    "TRIAL": "Andante",
    "BASIC": "Moderato",
    "INTERMEDIATE": "Allegretto",
    "ADVANCED": "Allegro",
}


def _reset_time(detail: dict[str, object]) -> datetime | None:
    for key in _RESET_KEYS:
        parsed = parse_timestamp(detail.get(key))
        if parsed is not None:
            return parsed
    return None


def _used_pct(detail: dict[str, object]) -> float | None:
    limit = as_number(detail.get("limit"))
    if not limit or limit <= 0:
        return None
    used = as_number(detail.get("used"))
    if used is None:
        remaining = as_number(detail.get("remaining"))
        if remaining is None:
            return None
        used = limit - remaining
    return max(0.0, min(100.0, used / limit * 100))


def _window_label(window: object) -> tuple[str, str] | None:
    if not isinstance(window, dict):
        return None
    duration = as_number(window.get("duration"))
    unit = _MINUTES_PER_UNIT.get(str(window.get("timeUnit")))
    if not duration or unit is None:
        return None
    minutes = duration * unit
    if minutes % 1440 == 0:
        days = int(minutes // 1440)
        return (f"{days}d", f"{days}d")
    if minutes % 60 == 0:
        hours = int(minutes // 60)
        return (f"{hours}h", f"{hours}h")
    return (f"{int(minutes)}m", f"{int(minutes)}m")


def _plan(payload: dict[str, object]) -> str | None:
    plan_name = payload.get("planName")
    if isinstance(plan_name, str) and plan_name.strip():
        return plan_name.strip()
    user = payload.get("user")
    membership = user.get("membership") if isinstance(user, dict) else None
    level = membership.get("level") if isinstance(membership, dict) else None
    if not isinstance(level, str) or not level:
        return None
    level = level.removeprefix("LEVEL_")
    return _PLAN_NAMES.get(level.upper()) or format_plan(level)


def _windows(payload: dict[str, object]) -> list[UsageWindow]:
    windows: list[UsageWindow] = []
    limits = payload.get("limits")
    if isinstance(limits, list):
        for item in limits[:1]:
            if not isinstance(item, dict) or not isinstance(item.get("detail"), dict):
                continue
            detail = item["detail"]
            used = _used_pct(detail)
            if used is None:
                continue
            label, short = _window_label(item.get("window")) or ("5h", "5h")
            windows.append(
                UsageWindow(
                    key="session",
                    label=label,
                    short=short,
                    used_pct=used,
                    resets_at=_reset_time(detail),
                )
            )
    usage = payload.get("usage")
    if isinstance(usage, dict):
        used = _used_pct(usage)
        if used is not None:
            windows.append(
                UsageWindow(
                    key="weekly",
                    label="Weekly",
                    short="wk",
                    used_pct=used,
                    resets_at=_reset_time(usage),
                )
            )
    return windows


def _usage_url(base_url: str) -> str:
    path = base_url.rstrip("/")
    if path.endswith("/coding/v1"):
        return f"{path}/usages"
    if path.endswith("/coding"):
        return f"{path}/v1/usages"
    return f"{path}/coding/v1/usages"


def _ascii(value: str, fallback: str = "unknown") -> str:
    cleaned = "".join(ch for ch in value if 0x20 <= ord(ch) <= 0x7E).strip()
    return cleaned or fallback


def _version() -> str:
    try:
        return metadata.version("quotabubble")
    except metadata.PackageNotFoundError:
        return "development"


def _identity_headers() -> dict[str, str]:
    return {
        "User-Agent": f"QuotaBubble/{_version()}",
        "X-Msh-Platform": "kimi_code_cli",
        "X-Msh-Version": _version(),
        "X-Msh-Device-Name": _ascii(socket.gethostname()),
        "X-Msh-Device-Model": _ascii(sys.platform),
        "X-Msh-Device-Id": kimi_code_device_id(),
    }


class KimiProvider:
    id = "kimi"
    display_name = "Kimi"
    uses_api_key = True

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx2.Client | None = None,
        login_reader: Callable[[], KimiCodeLogin | None] = read_kimi_code_login,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._read_login = login_reader
        self._clock = clock

    def detect(self) -> bool:
        return bool(self._api_key) or self._read_login() is not None

    def fetch(self) -> UsageSnapshot:
        if self._api_key:
            return self._request(self._api_key, from_login=False)
        login = self._read_login()
        if login is None:
            return self._snapshot(
                ProviderStatus.NO_CREDENTIALS, "Sign in with Kimi Code or add an API key"
            )
        if not login.is_fresh(self._clock()):
            return self._snapshot(
                ProviderStatus.EXPIRED, "Open Kimi Code to refresh your login"
            )
        return self._request(login.access_token, from_login=True)

    def check_api_key(self, api_key: str) -> KeyStatus:
        if not api_key:
            return KeyStatus.MISSING
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(
                _usage_url(kimi_code_base_url() or DEFAULT_BASE_URL),
                headers=self._headers(api_key),
            )
        except httpx2.HTTPError:
            return KeyStatus.UNREACHABLE
        finally:
            if self._client is None:
                client.close()
        if response.status_code in (401, 403):
            return KeyStatus.INVALID
        return KeyStatus.VALID if response.status_code == 200 else KeyStatus.UNREACHABLE

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            **_identity_headers(),
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    def _request(self, token: str, *, from_login: bool) -> UsageSnapshot:
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._query(token, client, from_login)
        finally:
            if self._client is None:
                client.close()

    def _query(self, token: str, client: httpx2.Client, from_login: bool) -> UsageSnapshot:
        base_url = kimi_code_base_url()
        if base_url is None and from_login:
            return self._snapshot(
                ProviderStatus.ERROR,
                "Unknown Kimi Code region; set KIMI_CODE_BASE_URL to your Kimi Code API host",
            )
        try:
            response = client.get(
                _usage_url(base_url or DEFAULT_BASE_URL), headers=self._headers(token)
            )
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        if response.status_code in (401, 403):
            if from_login:
                return self._snapshot(
                    ProviderStatus.EXPIRED, "Open Kimi Code to refresh your login"
                )
            return self._snapshot(ProviderStatus.ERROR, "Invalid Kimi Code API key")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected usage response")
        if not isinstance(payload, dict):
            return self._snapshot(ProviderStatus.ERROR, "Unexpected usage response")
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=_windows(payload),
            plan=_plan(payload),
        )

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
