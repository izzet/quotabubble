from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx2

from quotabubble.providers.base import (
    KeyStatus,
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    as_number,
    parse_timestamp,
)

QUOTA_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
REQUEST_TIMEOUT_SECONDS = 15.0
_MINUTES_PER_UNIT = {1: 1440, 3: 60, 5: 1, 6: 10080}
_PLAN_KEYS = ("planName", "plan", "plan_type", "packageName", "level")
_SESSION_MINUTES = 300
_RESET_SLACK = timedelta(minutes=1)


def _minutes(item: dict[str, object]) -> float:
    number = as_number(item.get("number")) or 0.0
    unit = _MINUTES_PER_UNIT.get(int(as_number(item.get("unit")) or 0), 0)
    return number * unit


def _used_pct(item: dict[str, object]) -> float:
    total = as_number(item.get("usage"))
    if total and total > 0:
        used = as_number(item.get("currentValue"))
        if used is None:
            remaining = as_number(item.get("remaining"))
            used = total - remaining if remaining is not None else None
        if used is not None:
            return max(0.0, min(100.0, used / total * 100))
    return max(0.0, min(100.0, as_number(item.get("percentage")) or 0.0))


def _reset(item: dict[str, object], minutes: float, now: datetime) -> datetime | None:
    reset = parse_timestamp(item.get("nextResetTime"))
    if reset is None:
        return None
    if minutes and reset - now > timedelta(minutes=minutes) + _RESET_SLACK:
        return None
    return reset


def _plan(data: dict[str, object]) -> str | None:
    for key in _PLAN_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _windows(data: dict[str, object], now: datetime) -> list[UsageWindow]:
    limits = data.get("limits")
    if not isinstance(limits, list):
        return []
    token_items = [
        item
        for item in limits
        if isinstance(item, dict) and item.get("type") in ("TOKENS_LIMIT", "CREDIT_LIMIT")
    ]
    token_items.sort(key=_minutes)
    windows: list[UsageWindow] = []
    for index, item in enumerate(token_items):
        minutes = _minutes(item)
        weekly = len(token_items) > 1 and index == len(token_items) - 1
        if weekly:
            label, short, key = "Weekly", "wk", "weekly"
        elif minutes == _SESSION_MINUTES or len(token_items) == 1:
            label, short, key = "5h", "5h", "session"
        else:
            label, short, key = "Tokens", "tok", "tokens"
        windows.append(
            UsageWindow(
                key=key,
                label=label,
                short=short,
                used_pct=_used_pct(item),
                resets_at=_reset(item, minutes, now),
            )
        )
    for item in limits:
        if isinstance(item, dict) and item.get("type") == "TIME_LIMIT":
            windows.append(
                UsageWindow(
                    key="mcp",
                    label="MCP",
                    short="mcp",
                    used_pct=_used_pct(item),
                    resets_at=_reset(item, _minutes(item), now),
                )
            )
    return windows


class ZaiProvider:
    id = "zai"
    display_name = "Z.ai"
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
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Add a Z.ai API key")
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
            response = client.get(QUOTA_URL, headers=self._headers(api_key))
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
            response = client.get(QUOTA_URL, headers=self._headers(api_key))
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.ERROR, "Invalid Z.ai API key")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected quota response")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return self._snapshot(ProviderStatus.ERROR, "Unexpected quota response")
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=_windows(data, datetime.now(tz=UTC)),
            plan=_plan(data),
        )

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
