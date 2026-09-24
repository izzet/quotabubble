from __future__ import annotations

from collections.abc import Callable

import httpx2

from quotabubble.credentials.zed import read_zed_credentials
from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    as_number,
    format_plan,
    parse_timestamp,
)

USER_URL = "https://cloud.zed.dev/client/users/me"
REQUEST_TIMEOUT_SECONDS = 15.0
_PLAN_NAMES = {
    "zed_free": "Free",
    "zed_pro": "Pro",
    "zed_pro_trial": "Pro Trial",
    "zed_student": "Student",
    "zed_business": "Business",
}


def _limit(value: object) -> float | None:
    """The edit-prediction limit: a number, {"limited": n}, or "unlimited"."""
    if isinstance(value, dict):
        value = value.get("limited")
    limit = as_number(value)
    return limit if limit and limit > 0 else None


def _plan(plan: dict[str, object]) -> str | None:
    name = plan.get("plan_v3") or plan.get("plan")
    if not isinstance(name, str) or not name:
        return None
    return _PLAN_NAMES.get(name) or format_plan(name.removeprefix("zed_"))


def _windows(plan: dict[str, object]) -> list[UsageWindow]:
    usage = plan.get("usage")
    predictions = usage.get("edit_predictions") if isinstance(usage, dict) else None
    if not isinstance(predictions, dict):
        return []
    limit = _limit(predictions.get("limit"))
    used = as_number(predictions.get("used"))
    if limit is None or used is None:
        return []
    period = plan.get("subscription_period")
    ends_at = parse_timestamp(period.get("ended_at")) if isinstance(period, dict) else None
    return [
        UsageWindow(
            key="edits",
            label="Edits",
            short="edit",
            used_pct=max(0.0, min(100.0, used / limit * 100)),
            resets_at=ends_at,
        )
    ]


class ZedProvider:
    id = "zed"
    display_name = "Zed"
    uses_api_key = False

    def __init__(
        self,
        credentials_reader: Callable[[], tuple[str, str] | None] = read_zed_credentials,
        client: httpx2.Client | None = None,
    ) -> None:
        self._read_credentials = credentials_reader
        self._client = client

    def detect(self) -> bool:
        return self._read_credentials() is not None

    def fetch(self) -> UsageSnapshot:
        credentials = self._read_credentials()
        if credentials is None:
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Sign in to Zed")
        user_id, token = credentials
        headers = {"Authorization": f"{user_id} {token}", "Accept": "application/json"}
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return self._query(headers, client)
        finally:
            if self._client is None:
                client.close()

    def _query(self, headers: dict[str, str], client: httpx2.Client) -> UsageSnapshot:
        try:
            response = client.get(USER_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Sign in to Zed again")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected account response")
        plan = payload.get("plan") if isinstance(payload, dict) else None
        if not isinstance(plan, dict):
            return self._snapshot(ProviderStatus.ERROR, "Unexpected account response")
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=_windows(plan),
            plan=_plan(plan),
        )

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
