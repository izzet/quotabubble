from __future__ import annotations

from datetime import UTC, datetime

import httpx2

from quotabubble.providers.base import (
    KeyStatus,
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    format_plan,
)

USAGE_URL = "https://api.kimi.com/coding/v1/usages"
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


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _reset_time(detail: dict[str, object]) -> datetime | None:
    for key in _RESET_KEYS:
        value = detail.get(key)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        number = _number(value)
        if number is not None:
            seconds = number / 1000 if number > 1e11 else number
            return datetime.fromtimestamp(seconds, tz=UTC)
    return None


def _used_pct(detail: dict[str, object]) -> float | None:
    limit = _number(detail.get("limit"))
    if not limit or limit <= 0:
        return None
    used = _number(detail.get("used"))
    if used is None:
        remaining = _number(detail.get("remaining"))
        if remaining is None:
            return None
        used = limit - remaining
    return max(0.0, min(100.0, used / limit * 100))


def _window_label(window: object) -> tuple[str, str] | None:
    if not isinstance(window, dict):
        return None
    duration = _number(window.get("duration"))
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


class KimiProvider:
    id = "kimi"
    display_name = "Kimi"
    uses_api_key = True

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client

    def detect(self) -> bool:
        return bool(self._api_key)

    def fetch(self) -> UsageSnapshot:
        if not self._api_key:
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Add a Kimi Code API key")
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._query(self._api_key, client)
        finally:
            if self._client is None:
                client.close()

    def check_api_key(self, api_key: str) -> KeyStatus:
        if not api_key:
            return KeyStatus.MISSING
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(USAGE_URL, headers=self._headers(api_key))
        except httpx2.HTTPError:
            return KeyStatus.UNREACHABLE
        finally:
            if self._client is None:
                client.close()
        if response.status_code in (401, 403):
            return KeyStatus.INVALID
        return KeyStatus.VALID if response.status_code == 200 else KeyStatus.UNREACHABLE

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    def _query(self, api_key: str, client: httpx2.Client) -> UsageSnapshot:
        try:
            response = client.get(USAGE_URL, headers=self._headers(api_key))
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        if response.status_code in (401, 403):
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
