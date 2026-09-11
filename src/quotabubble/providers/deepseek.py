from __future__ import annotations

import httpx2
from pydantic import BaseModel

from quotabubble.providers.base import Credits, KeyStatus, ProviderStatus, UsageSnapshot

BALANCE_URL = "https://api.deepseek.com/user/balance"
REQUEST_TIMEOUT_SECONDS = 15.0


class _BalanceInfo(BaseModel):
    currency: str | None = None
    total_balance: str | None = None
    granted_balance: str | None = None
    topped_up_balance: str | None = None


class _BalanceResponse(BaseModel):
    is_available: bool = False
    balance_infos: list[_BalanceInfo] = []


def _as_float(value: object) -> float | None:
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


def _credits(balance: _BalanceResponse) -> Credits | None:
    if not balance.balance_infos:
        return None
    infos = balance.balance_infos
    info = next(
        (item for item in infos if (item.currency or "").upper() == "USD"),
        infos[0],
    )
    amount = _as_float(info.total_balance)
    if amount is None:
        return None
    currency = (info.currency or "").upper()
    display = f"${amount:.2f}" if currency == "USD" else f"{amount:.2f} {currency}".strip()
    return Credits(display=display)


class DeepSeekProvider:
    id = "deepseek"
    display_name = "DeepSeek"
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
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "Add a DeepSeek API key")
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
            response = client.get(BALANCE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.ERROR, "Invalid DeepSeek API key")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            balance = _BalanceResponse.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected balance response")

        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            credits=_credits(balance),
        )

    def _status_for(self, api_key: str, client: httpx2.Client) -> KeyStatus:
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = client.get(BALANCE_URL, headers=headers)
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
