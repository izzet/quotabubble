from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ProviderStatus(StrEnum):
    LOADING = "loading"
    OK = "ok"
    NO_CREDENTIALS = "no_credentials"
    EXPIRED = "expired"
    ERROR = "error"


class KeyStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNREACHABLE = "unreachable"
    MISSING = "missing"


class UsageWindow(BaseModel):
    label: str
    used_pct: float
    key: str = ""
    short: str | None = None
    resets_at: datetime | None = None
    scope: str | None = None
    severity: str | None = None
    active: bool = False


class Credits(BaseModel):
    display: str
    used_pct: float | None = None


class UsageSnapshot(BaseModel):
    provider: str
    display_name: str
    status: ProviderStatus = ProviderStatus.OK
    windows: list[UsageWindow] = Field(default_factory=list)
    credits: Credits | None = None
    plan: str | None = None
    message: str | None = None
    stale: bool = False
    retry_after: float | None = None
    fetched_at: datetime | None = None


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def format_plan(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("_", " ").title()


def snapshot_windows(snapshot: UsageSnapshot) -> list[UsageWindow]:
    """Windows to track for a snapshot, synthesizing a 'Credits' window for
    credit-only providers (e.g. OpenRouter) that report no rate-limit windows."""
    windows = list(snapshot.windows)
    if not windows and snapshot.credits and snapshot.credits.used_pct is not None:
        windows.append(
            UsageWindow(label="Credits", key="credits", used_pct=snapshot.credits.used_pct)
        )
    return windows


@runtime_checkable
class Provider(Protocol):
    id: str
    display_name: str
    uses_api_key: bool

    def detect(self) -> bool: ...

    def fetch(self) -> UsageSnapshot: ...


@runtime_checkable
class ApiKeyProvider(Protocol):
    id: str
    display_name: str
    uses_api_key: bool

    def detect(self) -> bool: ...

    def fetch(self) -> UsageSnapshot: ...

    def check_api_key(self, api_key: str) -> KeyStatus: ...
