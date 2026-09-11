from __future__ import annotations

import httpx2
from pydantic import BaseModel

from quotabubble.providers.base import Credits, KeyStatus, ProviderStatus, UsageSnapshot

CREDITS_URL = "https://openrouter.ai/api/v1/credits"
REQUEST_TIMEOUT_SECONDS = 15.0


class _CreditsData(BaseModel):
    total_credits: float | None = None
    total_usage: float | None = None


class _CreditsResponse(BaseModel):
    data: _CreditsData | None = None


def _credits(response: _CreditsResponse) -> Credits | None:
    data = response.data
    if data is None or data.total_credits is None:
        return None
    remaining = max(0.0, data.total_credits - (data.total_usage or 0.0))
    return Credits(display=f"${remaining:.2f}")


class OpenRouterProvider:
    id = "openrouter"
    display_name = "OpenRouter"
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
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Add an OpenRouter API key")
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
            return self._status_for(api_key, client)
        finally:
            if self._client is None:
                client.close()

    def _query(self, api_key: str, client: httpx2.Client) -> UsageSnapshot:
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = client.get(CREDITS_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.ERROR, "Invalid OpenRouter API key")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            parsed = _CreditsResponse.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected credits response")

        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            credits=_credits(parsed),
        )

    def _status_for(self, api_key: str, client: httpx2.Client) -> KeyStatus:
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = client.get(CREDITS_URL, headers=headers)
        except httpx2.HTTPError:
            return KeyStatus.UNREACHABLE
        if response.status_code in (401, 403):
            return KeyStatus.INVALID
        if response.status_code != 200:
            return KeyStatus.UNREACHABLE
        return KeyStatus.VALID

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
