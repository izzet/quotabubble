from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MetricView(BaseModel):
    label: str
    compact_label: str | None = None
    percent: int | None = None
    bar_fraction: float | None = Field(default=None, ge=0, le=1)
    tone: Literal["ok", "warning", "critical", "muted"] = "muted"
    reset_text: str | None = None
    detail: str | None = None


class ProviderView(BaseModel):
    name: str
    trailing: str | None = None
    stale: bool = False
    compact_metrics: list[MetricView] = Field(default_factory=list)
    expanded_metrics: list[MetricView] = Field(default_factory=list)


class BubbleView(BaseModel):
    version: Literal[1] = 1
    providers: list[ProviderView] = Field(default_factory=list)
