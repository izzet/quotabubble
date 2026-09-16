from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx2
from pydantic import BaseModel, Field

from quotabubble.credentials import resolve_opencode_api_key
from quotabubble.providers.base import (
    KeyStatus,
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
)

USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
REQUEST_TIMEOUT_SECONDS = 15.0
USER_AGENT = "QuotaBubble"


class _UsageWindowData(BaseModel):
    percent: float = Field(default=0.0)
    reset_in_sec: int | None = Field(default=None, alias="resetInSec")


class _UsageContainer(BaseModel):
    rolling: _UsageWindowData | None = None
    weekly: _UsageWindowData | None = None
    monthly: _UsageWindowData | None = None
    renews_at: datetime | None = Field(default=None, alias="renewsAt")


class _UsageResponse(BaseModel):
    usage: _UsageContainer | None = None
    rolling: _UsageWindowData | None = None
    weekly: _UsageWindowData | None = None
    monthly: _UsageWindowData | None = None
    renews_at: datetime | None = Field(default=None, alias="renewsAt")

    def container(self) -> _UsageContainer | None:
        if self.usage is not None:
            return self.usage
        if self.rolling is not None or self.weekly is not None or self.monthly is not None:
            return _UsageContainer(
                rolling=self.rolling,
                weekly=self.weekly,
                monthly=self.monthly,
                renews_at=self.renews_at,
            )
        return None


class OpenCodeProvider:
    id = "opencode"
    display_name = "OpenCode"
    uses_api_key = True

    def __init__(
        self,
        api_key: str | None = None,
        key_resolver: Callable[[], str | None] | None = None,
        clock: Callable[[], datetime] | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._explicit_key = api_key
        self._key_resolver = key_resolver or resolve_opencode_api_key
        self._clock = clock or (lambda: datetime.now(UTC))
        self._client = client

    def _resolve_key(self) -> str | None:
        if self._explicit_key:
            return self._explicit_key
        return self._key_resolver()

    def detect(self) -> bool:
        return self._resolve_key() is not None

    def fetch(self) -> UsageSnapshot:
        key = self._resolve_key()
        if not key:
            return self._snapshot(
                ProviderStatus.NO_CREDENTIALS, "Add an OpenCode API key"
            )

        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._query(key, client)
        finally:
            if self._client is None:
                client.close()

    def check_api_key(self, api_key: str) -> KeyStatus:
        cleaned = api_key.strip()
        if not cleaned:
            return KeyStatus.MISSING

        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._status_for(cleaned, client)
        finally:
            if self._client is None:
                client.close()

    def _status_for(self, api_key: str, client: httpx2.Client) -> KeyStatus:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError:
            return KeyStatus.UNREACHABLE

        if response.status_code == 200:
            return KeyStatus.VALID
        if response.status_code in (401, 403):
            return KeyStatus.INVALID
        return KeyStatus.UNREACHABLE

    def _query(self, api_key: str, client: httpx2.Client) -> UsageSnapshot:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Invalid OpenCode API key")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            parsed = _UsageResponse.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected OpenCode response")

        container = parsed.container()
        if container is None:
            return self._snapshot(ProviderStatus.ERROR, "Missing usage fields")

        now = self._clock()
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=self._windows(container, now),
        )

    @staticmethod
    def _windows(container: _UsageContainer, now: datetime) -> list[UsageWindow]:
        rolling = None
        if container.rolling is not None:
            rolling_resets = (
                now + timedelta(seconds=container.rolling.reset_in_sec)
                if container.rolling.reset_in_sec is not None
                else None
            )
            rolling = UsageWindow(
                key="rolling",
                label="5h",
                short="5h",
                used_pct=container.rolling.percent,
                resets_at=rolling_resets,
            )

        weekly = None
        if container.weekly is not None:
            weekly_resets = (
                now + timedelta(seconds=container.weekly.reset_in_sec)
                if container.weekly.reset_in_sec is not None
                else None
            )
            weekly = UsageWindow(
                key="weekly",
                label="Weekly",
                short="wk",
                used_pct=container.weekly.percent,
                resets_at=weekly_resets,
            )

        monthly = None
        if container.monthly is not None:
            monthly_resets = (
                now + timedelta(seconds=container.monthly.reset_in_sec)
                if container.monthly.reset_in_sec is not None
                else container.renews_at
            )
            monthly = UsageWindow(
                key="monthly",
                label="Monthly",
                short="mo",
                used_pct=container.monthly.percent,
                resets_at=monthly_resets,
            )

        windows: list[UsageWindow] = []
        if rolling is not None:
            windows.append(rolling)

        long_windows: list[UsageWindow] = []
        if weekly is not None and monthly is not None:
            if monthly.used_pct > weekly.used_pct:
                long_windows = [monthly, weekly]
            else:
                long_windows = [weekly, monthly]
        elif weekly is not None:
            long_windows = [weekly]
        elif monthly is not None:
            long_windows = [monthly]

        windows.extend(long_windows)
        return windows

    def _snapshot(
        self, status: ProviderStatus, message: str | None = None
    ) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
