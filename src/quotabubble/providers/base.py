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


class UsageWindow(BaseModel):
    label: str
    used_pct: float
    resets_at: datetime | None = None


class UsageSnapshot(BaseModel):
    provider: str
    display_name: str
    status: ProviderStatus = ProviderStatus.OK
    windows: list[UsageWindow] = Field(default_factory=list)
    message: str | None = None
    fetched_at: datetime | None = None


@runtime_checkable
class Provider(Protocol):
    id: str
    display_name: str

    def fetch(self) -> UsageSnapshot: ...
