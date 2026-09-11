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
    fetched_at: datetime | None = None


def format_plan(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("_", " ").title()


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
