from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import httpx2
from pydantic import BaseModel

from quotabubble.credentials import enumerate_generic_credentials
from quotabubble.credentials.copilot import read_copilot_cli_credentials
from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    format_plan,
)

USAGE_URL = "https://api.github.com/copilot_internal/user"
CREDENTIAL_TARGET_HINT = "copilot-cli"
REQUEST_TIMEOUT_SECONDS = 20.0
HEADERS = {
    "Accept": "application/json",
    "Editor-Version": "vscode/1.96.2",
    "Editor-Plugin-Version": "copilot-chat/0.26.7",
    "User-Agent": "GitHubCopilotChat/0.26.7",
    "X-Github-Api-Version": "2025-04-01",
}


class _QuotaSnapshot(BaseModel):
    entitlement: float | None = None
    remaining: float | None = None
    percent_remaining: float | None = None


class _QuotaSnapshots(BaseModel):
    premium_interactions: _QuotaSnapshot | None = None
    chat: _QuotaSnapshot | None = None


class _UserResponse(BaseModel):
    copilot_plan: str | None = None
    quota_reset_date: datetime | None = None
    quota_snapshots: _QuotaSnapshots | None = None


def _decode_token(blob: bytes) -> str | None:
    for encoding in ("utf-8", "utf-16-le"):
        try:
            text = blob.decode(encoding)
        except UnicodeDecodeError:
            continue
        text = text.strip("\x00").strip()
        if text and "\x00" not in text:
            return text
    return None


def _used_percent(snapshot: _QuotaSnapshot | None) -> float | None:
    if snapshot is None:
        return None
    if snapshot.percent_remaining is not None:
        return max(0.0, min(100.0, 100.0 - snapshot.percent_remaining))
    if snapshot.entitlement and snapshot.remaining is not None and snapshot.entitlement > 0:
        return max(0.0, min(100.0, (1.0 - snapshot.remaining / snapshot.entitlement) * 100.0))
    return None


def _default_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    linux_credentials = read_copilot_cli_credentials()
    return linux_credentials or enumerate_generic_credentials(name_contains)


class CopilotProvider:
    id = "copilot"
    display_name = "Copilot"
    uses_api_key = False

    def __init__(
        self,
        credential_provider: Callable[[str], list[tuple[str, bytes]]] | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._credentials = credential_provider or _default_credentials
        self._client = client

    def detect(self) -> bool:
        return self._token() is not None

    def fetch(self) -> UsageSnapshot:
        token = self._token()
        if token is None:
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "No Copilot token found")

        headers = {"Authorization": f"token {token}", **HEADERS}
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        finally:
            if self._client is None:
                client.close()

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Sign in with Copilot again")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            parsed = _UserResponse.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected Copilot response")

        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=self._windows(parsed),
            plan=format_plan(parsed.copilot_plan),
        )

    def _token(self) -> str | None:
        for _target, blob in self._credentials(CREDENTIAL_TARGET_HINT):
            token = _decode_token(blob)
            if token:
                return token
        return None

    @staticmethod
    def _windows(parsed: _UserResponse) -> list[UsageWindow]:
        snapshots = parsed.quota_snapshots
        if snapshots is None:
            return []
        windows: list[UsageWindow] = []
        premium = _used_percent(snapshots.premium_interactions)
        if premium is not None:
            windows.append(
                UsageWindow(
                    key="premium",
                    label="Premium",
                    short="pre",
                    used_pct=premium,
                    resets_at=parsed.quota_reset_date,
                )
            )
        chat = _used_percent(snapshots.chat)
        if chat is not None:
            windows.append(
                UsageWindow(
                    key="chat",
                    label="Chat",
                    short="ch",
                    used_pct=chat,
                    resets_at=parsed.quota_reset_date,
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
