from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx2

from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    as_number,
    parse_timestamp,
)

BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
SETTINGS_URL = "https://cli-chat-proxy.grok.com/v1/settings"
REQUEST_TIMEOUT_SECONDS = 15.0
SETTINGS_TIMEOUT_SECONDS = 2.0
_SCOPE_PREFERENCE = ("https://auth.x.ai::", "https://accounts.x.ai/sign-in")


def default_credentials_path() -> Path:
    grok_home = os.environ.get("GROK_HOME")
    base = Path(grok_home) if grok_home else Path.home() / ".grok"
    return base / "auth.json"


def read_credentials(path: Path) -> tuple[str, datetime | None] | None:
    """Return the CLI's bearer token and its expiry from ~/.grok/auth.json."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    for prefix in _SCOPE_PREFERENCE:
        for scope, entry in raw.items():
            if not scope.startswith(prefix) or not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if isinstance(key, str) and key:
                return key, parse_timestamp(entry.get("expires_at"))
    return None


def _value(node: object) -> float | None:
    if isinstance(node, dict):
        return as_number(node.get("val"))
    return as_number(node)


def _used_pct(config: dict[str, object]) -> float | None:
    percent = as_number(config.get("creditUsagePercent"))
    if percent is None:
        used = _value(config.get("onDemandUsed"))
        cap = _value(config.get("onDemandCap"))
        if used is None or not cap or cap <= 0:
            return None
        percent = used / cap * 100
    return max(0.0, min(100.0, percent))


def _reset(config: dict[str, object]) -> datetime | None:
    period = config.get("currentPeriod")
    if isinstance(period, dict):
        parsed = parse_timestamp(period.get("end"))
        if parsed is not None:
            return parsed
    return parse_timestamp(config.get("billingPeriodEnd"))


class GrokProvider:
    id = "grok"
    display_name = "Grok"
    uses_api_key = False

    def __init__(
        self,
        credentials_path: Path | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._credentials_path = credentials_path or default_credentials_path()
        self._client = client

    def detect(self) -> bool:
        return read_credentials(self._credentials_path) is not None

    def fetch(self) -> UsageSnapshot:
        credentials = read_credentials(self._credentials_path)
        if credentials is None:
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Run `grok login`")
        token, expires_at = credentials
        if expires_at is not None and expires_at <= datetime.now(tz=UTC):
            return self._snapshot(ProviderStatus.EXPIRED, "Run `grok login` again")

        headers = {
            "Authorization": f"Bearer {token}",
            "x-xai-token-auth": "xai-grok-cli",
            "Accept": "application/json",
        }
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._query(headers, client)
        finally:
            if self._client is None:
                client.close()

    def _query(self, headers: dict[str, str], client: httpx2.Client) -> UsageSnapshot:
        try:
            response = client.get(BILLING_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Run `grok login` again")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected billing response")
        config = payload.get("config") if isinstance(payload, dict) else None
        if not isinstance(config, dict):
            return self._snapshot(ProviderStatus.ERROR, "Unexpected billing response")

        windows: list[UsageWindow] = []
        used = _used_pct(config)
        if used is not None:
            windows.append(
                UsageWindow(
                    key="credits",
                    label="Credits",
                    short="cr",
                    used_pct=used,
                    resets_at=_reset(config),
                )
            )
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=windows,
            plan=self._plan(headers, client) or self._fallback_plan(config),
        )

    @staticmethod
    def _plan(headers: dict[str, str], client: httpx2.Client) -> str | None:
        try:
            response = client.get(SETTINGS_URL, headers=headers, timeout=SETTINGS_TIMEOUT_SECONDS)
            payload = response.json() if response.status_code == 200 else None
        except (httpx2.HTTPError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        tier = payload.get("subscription_tier_display")
        return tier.strip() if isinstance(tier, str) and tier.strip() else None

    @staticmethod
    def _fallback_plan(config: dict[str, object]) -> str | None:
        tier = config.get("subscriptionTier")
        return tier.strip() if isinstance(tier, str) and tier.strip() else None

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
