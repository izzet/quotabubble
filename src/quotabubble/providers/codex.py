from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel

from quotabubble.providers.base import Credits, ProviderStatus, UsageSnapshot, UsageWindow

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
USER_AGENT = "codex-cli"
REQUEST_TIMEOUT_SECONDS = 15.0
WEEKLY_WINDOW_THRESHOLD_SECONDS = 86_400
_WINDOW_ORDER = {"session": 0, "weekly": 1}


class _TokenData(BaseModel):
    access_token: str
    account_id: str | None = None


class _AuthFile(BaseModel):
    tokens: _TokenData | None = None


class _RateLimitWindow(BaseModel):
    used_percent: float
    reset_at: int | None = None
    limit_window_seconds: int | None = None


class _RateLimitDetails(BaseModel):
    primary_window: _RateLimitWindow | None = None
    secondary_window: _RateLimitWindow | None = None


class _Credits(BaseModel):
    has_credits: bool = False
    unlimited: bool = False
    balance: str | None = None


class _UsageResponse(BaseModel):
    plan_type: str | None = None
    rate_limit: _RateLimitDetails | None = None
    credits: _Credits | None = None


def default_credentials_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home) if codex_home else Path.home() / ".codex"
    return base / "auth.json"


def read_credentials(path: Path) -> _TokenData | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        auth = _AuthFile.model_validate(raw)
    except ValueError:
        return None
    tokens = auth.tokens
    if tokens is None or not tokens.access_token:
        return None
    return tokens


def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _window_key(window: _RateLimitWindow, default_is_weekly: bool) -> str:
    if window.limit_window_seconds is not None:
        is_weekly = window.limit_window_seconds >= WEEKLY_WINDOW_THRESHOLD_SECONDS
    else:
        is_weekly = default_is_weekly
    return "weekly" if is_weekly else "session"


def _credits(credits: _Credits | None) -> Credits | None:
    if credits is None:
        return None
    if credits.unlimited:
        return Credits(display="Unlimited")
    if credits.has_credits and credits.balance is not None:
        return Credits(display=credits.balance)
    return None


class CodexProvider:
    id = "codex"
    display_name = "Codex"

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
            return self._snapshot(ProviderStatus.NO_CREDENTIALS, "No Codex credentials found")

        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "User-Agent": USER_AGENT,
        }
        if credentials.account_id:
            headers["ChatGPT-Account-Id"] = credentials.account_id

        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            response = client.get(USAGE_URL, headers=headers)
        except httpx2.HTTPError as exc:
            return self._snapshot(ProviderStatus.ERROR, str(exc))
        finally:
            if self._client is None:
                client.close()

        if response.status_code in (401, 403):
            return self._snapshot(ProviderStatus.EXPIRED, "Sign in with Codex again")
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
            credits=_credits(parsed.credits),
            plan=parsed.plan_type,
        )

    def _windows(self, parsed: _UsageResponse) -> list[UsageWindow]:
        if parsed.rate_limit is None:
            return []

        windows: list[UsageWindow] = []
        candidates = (
            (parsed.rate_limit.primary_window, False),
            (parsed.rate_limit.secondary_window, True),
        )
        for window, default_is_weekly in candidates:
            if window is None:
                continue
            key = _window_key(window, default_is_weekly)
            windows.append(
                UsageWindow(
                    key=key,
                    label="Weekly" if key == "weekly" else "5h",
                    used_pct=window.used_percent,
                    resets_at=_to_datetime(window.reset_at),
                )
            )

        windows.sort(key=lambda item: (_WINDOW_ORDER.get(item.key, 2), item.label))
        return windows

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
