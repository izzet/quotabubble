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


class AppearanceView(BaseModel):
    idle_opacity: float = Field(ge=0, le=1)
    hover_opacity: float = Field(ge=0, le=1)
    fade_delay_ms: int = Field(ge=0)
    fade_duration_ms: int = Field(ge=0)


class BubbleView(BaseModel):
    version: Literal[1] = 1
    appearance: AppearanceView
    providers: list[ProviderView] = Field(default_factory=list)
    position: tuple[int, int] | None = None
