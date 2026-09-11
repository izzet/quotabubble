from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import httpx2
from pydantic import BaseModel, Field

from quotabubble.credentials import read_generic_credential
from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    format_plan,
)

CREDENTIAL_TARGET = "gemini:antigravity"
ENDPOINTS = (
    "https://daily-cloudcode-pa.googleapis.com",
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
    "https://cloudcode-pa.googleapis.com",
)
USER_AGENT = "antigravity"
REQUEST_TIMEOUT_SECONDS = 20.0
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
EXPIRY_SKEW_SECONDS = 60
_WINDOW_LABELS = {"5h": ("session", "5h"), "weekly": ("weekly", "Weekly")}
_WINDOW_ORDER = {"session": 0, "weekly": 1}
_DISPLAY_MODEL_PREFIXES = ("gemini", "claude", "gpt", "image", "imagen")
_CLIENT_SUFFIX = b".apps.googleusercontent.com"
_SECRET_PREFIX = b"GOCSPX-"


class _AuthError(Exception):
    pass


class _Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expiry: datetime | None = None


class _AuthFile(BaseModel):
    token: _Token


class _Tier(BaseModel):
    name: str | None = None


class _LoadResponse(BaseModel):
    project: str | None = Field(default=None, alias="cloudaicompanionProject")
    current_tier: _Tier | None = Field(default=None, alias="currentTier")


class _Bucket(BaseModel):
    window: str | None = None
    bucket_id: str | None = Field(default=None, alias="bucketId")
    display_name: str | None = Field(default=None, alias="displayName")
    remaining_fraction: float | None = Field(default=None, alias="remainingFraction")
    reset_time: datetime | None = Field(default=None, alias="resetTime")


class _Group(BaseModel):
    display_name: str | None = Field(default=None, alias="displayName")
    description: str | None = None
    buckets: list[_Bucket] = Field(default_factory=list)


class _SummaryResponse(BaseModel):
    groups: list[_Group] = Field(default_factory=list)


class _QuotaInfo(BaseModel):
    remaining_fraction: float | None = Field(default=None, alias="remainingFraction")
    reset_time: datetime | None = Field(default=None, alias="resetTime")


class _ModelInfo(BaseModel):
    quota_info: _QuotaInfo | None = Field(default=None, alias="quotaInfo")


class _ModelsResponse(BaseModel):
    models: dict[str, _ModelInfo] = Field(default_factory=dict)


def _is_token_byte(value: int) -> bool:
    return (
        48 <= value <= 57
        or 65 <= value <= 90
        or 97 <= value <= 122
        or value in (45, 95)
    )


def _scan_client_ids(data: bytes) -> list[str]:
    ids: list[str] = []
    index = 0
    while True:
        position = data.find(_CLIENT_SUFFIX, index)
        if position < 0:
            break
        end = position + len(_CLIENT_SUFFIX)
        start = position
        while start > 0 and _is_token_byte(data[start - 1]):
            start -= 1
        segment = data[start:end]
        last_dash = segment.rfind(b"-")
        if last_dash >= 0:
            head = start + last_dash
            while head > start and 48 <= data[head - 1] <= 57:
                head -= 1
            start = head
        try:
            candidate = data[start:end].decode("utf-8")
        except UnicodeDecodeError:
            candidate = ""
        if (
            candidate.endswith(".apps.googleusercontent.com")
            and candidate.split("-", 1)[0].isdigit()
            and candidate not in ids
        ):
            ids.append(candidate)
        index = end
    return ids


def _scan_client_secrets(data: bytes) -> list[str]:
    secrets: list[str] = []
    total = len(_SECRET_PREFIX) + 28
    index = 0
    while True:
        position = data.find(_SECRET_PREFIX, index)
        if position < 0:
            break
        candidate = data[position : position + total]
        if len(candidate) == total and all(
            _is_token_byte(value) for value in candidate[len(_SECRET_PREFIX) :]
        ):
            text = candidate.decode("utf-8")
            if text not in secrets:
                secrets.append(text)
        index = position + len(_SECRET_PREFIX)
    return secrets


def _agy_paths() -> list[Path]:
    paths: list[Path] = []
    found = shutil.which("agy")
    if found:
        paths.append(Path(found))
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        paths.append(Path(local_appdata) / "agy" / "bin" / "agy.exe")
    return paths


@lru_cache(maxsize=1)
def _discover_oauth_clients() -> tuple[tuple[str, str], ...]:
    for path in _agy_paths():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        ids = _scan_client_ids(data)
        secrets = _scan_client_secrets(data)
        combos = tuple(
            (client_id, secret) for client_id in ids for secret in secrets
        )
        if combos:
            return combos
    return ()


def _is_expired(expiry: datetime | None) -> bool:
    if expiry is None:
        return True
    now = datetime.now(tz=expiry.tzinfo or UTC)
    return expiry <= now + timedelta(seconds=EXPIRY_SKEW_SECONDS)


def _used_from_remaining(remaining: float | None) -> float | None:
    if remaining is None:
        return None
    return (1.0 - max(0.0, min(1.0, remaining))) * 100.0


def _windows_from_group(group: _Group) -> list[UsageWindow]:
    windows: list[UsageWindow] = []
    for bucket in group.buckets:
        if bucket.window is None:
            continue
        labels = _WINDOW_LABELS.get(bucket.window.lower())
        used = _used_from_remaining(bucket.remaining_fraction)
        if labels is None or used is None:
            continue
        key, label = labels
        windows.append(
            UsageWindow(key=key, label=label, used_pct=used, resets_at=bucket.reset_time)
        )
    return windows


def _is_gemini_group(group: _Group) -> bool:
    if group.display_name and "gemini" in group.display_name.lower():
        return True
    if group.description and "gemini" in group.description.lower():
        return True
    return any(
        (bucket.bucket_id is not None and bucket.bucket_id.lower().startswith("gemini-"))
        or (bucket.display_name is not None and "gemini" in bucket.display_name.lower())
        for bucket in group.buckets
    )


def _windows_from_summary(response: _SummaryResponse) -> list[UsageWindow]:
    fallback: list[UsageWindow] | None = None
    for group in response.groups:
        windows = _windows_from_group(group)
        if not windows:
            continue
        windows.sort(key=lambda window: _WINDOW_ORDER.get(window.key, 2))
        if _is_gemini_group(group):
            return windows
        if fallback is None:
            fallback = windows
    return fallback or []


def _best_model_window(response: _ModelsResponse) -> list[UsageWindow]:
    candidates: list[UsageWindow] = []
    for model, info in response.models.items():
        if info.quota_info is None:
            continue
        used = _used_from_remaining(info.quota_info.remaining_fraction)
        if used is None or not model.lower().startswith(_DISPLAY_MODEL_PREFIXES):
            continue
        candidates.append(
            UsageWindow(
                key="session",
                label="5h",
                used_pct=used,
                resets_at=info.quota_info.reset_time,
            )
        )
    if not candidates:
        return []
    return [max(candidates, key=lambda window: window.used_pct)]


class AntigravityProvider:
    id = "antigravity"
    display_name = "Antigravity"
    uses_api_key = False

    def __init__(
        self,
        credential_reader: Callable[[str], bytes | None] | None = None,
        oauth_clients_provider: Callable[[], Sequence[tuple[str, str]]] | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._read_credential = credential_reader or read_generic_credential
        self._oauth_clients_provider = oauth_clients_provider or _discover_oauth_clients
        self._client = client

    def detect(self) -> bool:
        return self._credentials() is not None

    def fetch(self) -> UsageSnapshot:
        credentials = self._credentials()
        if credentials is None:
            return self._snapshot(
                ProviderStatus.NO_CREDENTIALS, "No Antigravity credentials found"
            )

        client = self._client or httpx2.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            token = self._usable_token(client, credentials)
            if token is None:
                return self._snapshot(ProviderStatus.EXPIRED, "Sign in with Antigravity again")
            try:
                windows, plan = self._fetch_all(client, token)
            except _AuthError:
                refreshed = self._refresh(client, credentials)
                if refreshed is None:
                    return self._snapshot(
                        ProviderStatus.EXPIRED, "Sign in with Antigravity again"
                    )
                try:
                    windows, plan = self._fetch_all(client, refreshed)
                except _AuthError:
                    return self._snapshot(
                        ProviderStatus.EXPIRED, "Sign in with Antigravity again"
                    )
                except (httpx2.HTTPError, ValueError) as exc:
                    return self._snapshot(ProviderStatus.ERROR, str(exc))
            except (httpx2.HTTPError, ValueError) as exc:
                return self._snapshot(ProviderStatus.ERROR, str(exc))

            if not windows:
                return self._snapshot(ProviderStatus.ERROR, "Antigravity returned no quota")
            return UsageSnapshot(
                provider=self.id,
                display_name=self.display_name,
                windows=windows,
                plan=plan,
            )
        finally:
            if self._client is None:
                client.close()

    def _credentials(self) -> _AuthFile | None:
        blob = self._read_credential(CREDENTIAL_TARGET)
        if blob is None:
            return None
        try:
            return _AuthFile.model_validate_json(blob.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None

    def _usable_token(self, client: httpx2.Client, credentials: _AuthFile) -> str | None:
        token = credentials.token
        if token.refresh_token and _is_expired(token.expiry):
            refreshed = self._refresh(client, credentials)
            if refreshed:
                return refreshed
        return token.access_token or None

    def _refresh(self, client: httpx2.Client, credentials: _AuthFile) -> str | None:
        refresh_token = credentials.token.refresh_token
        if not refresh_token:
            return None
        for client_id, client_secret in self._oauth_clients_provider():
            try:
                response = client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            except httpx2.HTTPError:
                continue
            if response.status_code != 200:
                continue
            try:
                payload = response.json()
            except ValueError:
                continue
            access_token = payload.get("access_token")
            if isinstance(access_token, str) and access_token:
                return access_token
        return None

    def _fetch_all(
        self, client: httpx2.Client, token: str
    ) -> tuple[list[UsageWindow], str | None]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        auth_error = False
        last_error: Exception | None = None
        for base in ENDPOINTS:
            try:
                windows, plan = self._collect(client, base, headers)
            except _AuthError:
                auth_error = True
                continue
            except (httpx2.HTTPError, ValueError) as exc:
                last_error = exc
                continue
            if windows:
                return windows, plan
        if auth_error:
            raise _AuthError
        if last_error is not None:
            raise last_error
        return [], None

    def _collect(
        self, client: httpx2.Client, base: str, headers: dict[str, str]
    ) -> tuple[list[UsageWindow], str | None]:
        load = self._load(client, base, headers)
        plan = format_plan(load.current_tier.name) if load.current_tier else None
        if plan is not None and plan.casefold() == self.display_name.casefold():
            plan = None
        project = load.project or None
        if project:
            try:
                windows = self._quota_summary(client, base, headers, project)
                if windows:
                    return windows, plan
            except _AuthError:
                raise
            except (httpx2.HTTPError, ValueError):
                pass
        return self._available_models(client, base, headers, project), plan

    def _load(
        self, client: httpx2.Client, base: str, headers: dict[str, str]
    ) -> _LoadResponse:
        body = {"metadata": {"ideType": "ANTIGRAVITY"}}
        data = self._post(client, f"{base}/v1internal:loadCodeAssist", headers, body)
        return _LoadResponse.model_validate(data)

    def _quota_summary(
        self, client: httpx2.Client, base: str, headers: dict[str, str], project: str
    ) -> list[UsageWindow]:
        body = {"project": project}
        data = self._post(client, f"{base}/v1internal:retrieveUserQuotaSummary", headers, body)
        return _windows_from_summary(_SummaryResponse.model_validate(data))

    def _available_models(
        self,
        client: httpx2.Client,
        base: str,
        headers: dict[str, str],
        project: str | None,
    ) -> list[UsageWindow]:
        body = {"project": project} if project else {}
        data = self._post(client, f"{base}/v1internal:fetchAvailableModels", headers, body)
        return _best_model_window(_ModelsResponse.model_validate(data))

    @staticmethod
    def _post(
        client: httpx2.Client, url: str, headers: dict[str, str], body: dict[str, object]
    ) -> object:
        response = client.post(url, headers=headers, json=body)
        if response.status_code in (401, 403):
            raise _AuthError
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        return response.json()

    def _snapshot(self, status: ProviderStatus, message: str | None = None) -> UsageSnapshot:
        return UsageSnapshot(
            provider=self.id,
            display_name=self.display_name,
            status=status,
            message=message,
        )
