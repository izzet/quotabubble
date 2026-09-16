from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import httpx2
from pydantic import BaseModel, Field

from quotabubble.credentials import resolve_cursor_session_token
from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    format_plan,
)

USAGE_URL = "https://cursor.com/api/usage-summary"
REQUEST_TIMEOUT_SECONDS = 15.0
HEADERS = {
    "Accept": "application/json",
    "Origin": "https://cursor.com",
    "Referer": "https://cursor.com/dashboard",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class _PlanUsage(BaseModel):
    enabled: bool = True
    auto_percent_used: float | None = Field(default=None, alias="autoPercentUsed")
    api_percent_used: float | None = Field(default=None, alias="apiPercentUsed")


class _IndividualUsage(BaseModel):
    plan: _PlanUsage | None = None


class _UsageSummary(BaseModel):
    billing_cycle_end: datetime | None = Field(default=None, alias="billingCycleEnd")
    membership_type: str | None = Field(default=None, alias="membershipType")
    is_unlimited: bool = Field(default=False, alias="isUnlimited")
    individual_usage: _IndividualUsage | None = Field(default=None, alias="individualUsage")


class CursorProvider:
    id = "cursor"
    display_name = "Cursor"
    uses_api_key = False

    def __init__(
        self,
        token_provider: Callable[[], str | None] | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._token_provider = token_provider or resolve_cursor_session_token
        self._client = client

    def detect(self) -> bool:
        return self._token_provider() is not None

    def fetch(self) -> UsageSnapshot:
        token = self._token_provider()
        if token is None:
            return self._snapshot(
                ProviderStatus.NO_CREDENTIALS, "No Cursor session token found"
            )

        headers = {**HEADERS, "Cookie": f"WorkosCursorSessionToken={token}"}
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        finally:
            if self._client is None:
                client.close()

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Sign in with Cursor again")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            parsed = _UsageSummary.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected Cursor response")

        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=self._windows(parsed),
            plan=format_plan(parsed.membership_type),
        )

    @staticmethod
    def _windows(parsed: _UsageSummary) -> list[UsageWindow]:
        if parsed.is_unlimited:
            return []
        plan = None if parsed.individual_usage is None else parsed.individual_usage.plan
        if plan is None or not plan.enabled:
            return []

        windows: list[UsageWindow] = []
        if plan.auto_percent_used is not None:
            windows.append(
                UsageWindow(
                    key="auto",
                    label="Auto",
                    short="auto",
                    used_pct=plan.auto_percent_used,
                    resets_at=parsed.billing_cycle_end,
                )
            )
        if plan.api_percent_used is not None:
            windows.append(
                UsageWindow(
                    key="api",
                    label="API",
                    short="api",
                    used_pct=plan.api_percent_used,
                    resets_at=parsed.billing_cycle_end,
                )
            )
        return windows

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
