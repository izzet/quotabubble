from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel

from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
ANTHROPIC_BETA = "oauth-2025-04-20"
REQUEST_TIMEOUT_SECONDS = 15.0


class _Bucket(BaseModel):
    utilization: float
    resets_at: datetime | None = None


class _UsageResponse(BaseModel):
    five_hour: _Bucket | None = None
    seven_day: _Bucket | None = None


def default_credentials_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def read_access_token(path: Path) -> str | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    oauth = raw.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None
    token = oauth.get("accessToken")
    if isinstance(token, str) and token:
        return token
    return None


class ClaudeProvider:
    id = "claude"
    display_name = "Claude"

    def __init__(
        self,
        credentials_path: Path | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._credentials_path = credentials_path or default_credentials_path()
        self._client = client

    def fetch(self) -> UsageSnapshot:
        token = read_access_token(self._credentials_path)
        if token is None:
            return self._snapshot(
                ProviderStatus.NO_CREDENTIALS, "No Claude Code credentials found"
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-beta": ANTHROPIC_BETA,
        }
        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        finally:
            if self._client is None:
                client.close()

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Sign in with Claude Code again")
        if response.status_code != 200:
            return self._snapshot(ProviderStatus.ERROR, f"HTTP {response.status_code}")

        try:
            parsed = _UsageResponse.model_validate(response.json())
        except ValueError:
            return self._snapshot(ProviderStatus.ERROR, "Unexpected usage response")

        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            windows=self._windows(parsed),
        )

    def _windows(self, parsed: _UsageResponse) -> list[UsageWindow]:
        windows: list[UsageWindow] = []
        if parsed.five_hour is not None:
            windows.append(
                UsageWindow(
                    label="5h",
                    used_pct=parsed.five_hour.utilization,
                    resets_at=parsed.five_hour.resets_at,
                )
            )
        if parsed.seven_day is not None:
            windows.append(
                UsageWindow(
                    label="7d",
                    used_pct=parsed.seven_day.utilization,
                    resets_at=parsed.seven_day.resets_at,
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
