from __future__ import annotations

from datetime import datetime

from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow

from .formatting import format_age, format_reset
from .models import AppearanceView, BubbleView, MetricView, ProviderView


def build_bubble_view(
    snapshots: list[UsageSnapshot], settings: Settings, *, now: datetime | None = None
) -> BubbleView:
    return BubbleView(
        appearance=AppearanceView(
            idle_opacity=settings.idle_opacity,
            hover_opacity=settings.hover_opacity,
            fade_delay_ms=settings.fade_delay_ms,
            fade_duration_ms=settings.fade_duration_ms,
        ),
        providers=[_provider_view(snapshot, settings, now=now) for snapshot in snapshots],
        position=settings.position,
    )


def _provider_view(
    snapshot: UsageSnapshot, settings: Settings, *, now: datetime | None
) -> ProviderView:
    trailing = snapshot.plan
    if snapshot.stale:
        age = format_age(snapshot.fetched_at, now=now)
        trailing = " · ".join(value for value in (trailing, age) if value)

    if snapshot.status is not ProviderStatus.OK:
        status = _status_text(snapshot.status)
        metrics = [MetricView(label=status)]
        if snapshot.credits is not None:
            metrics.append(MetricView(label="Credits", detail=snapshot.credits.display))
        return ProviderView(
            name=snapshot.display_name,
            trailing=trailing,
            stale=snapshot.stale,
            compact_metrics=metrics[:1],
            expanded_metrics=metrics,
        )

    metrics = [_metric_view(window, settings, now=now) for window in snapshot.windows]
    if snapshot.credits is not None:
        metrics.append(MetricView(label="Credits", detail=snapshot.credits.display))
    if not metrics:
        metrics.append(MetricView(label="—"))

    return ProviderView(
        name=snapshot.display_name,
        trailing=trailing,
        stale=snapshot.stale,
        compact_metrics=metrics[:2],
        expanded_metrics=metrics,
    )


def _metric_view(window: UsageWindow, settings: Settings, *, now: datetime | None) -> MetricView:
    percent = 100 - window.used_pct if settings.show_remaining else window.used_pct
    return MetricView(
        label=window.label,
        compact_label=window.short,
        percent=round(percent),
        bar_fraction=max(0, min(1, percent / 100)),
        tone=_tone(window),
        reset_text=format_reset(window.resets_at, now=now),
    )


def _tone(window: UsageWindow) -> str:
    if window.severity == "critical" or window.used_pct >= 85:
        return "critical"
    if window.used_pct >= 60:
        return "warning"
    return "ok"


def _status_text(status: ProviderStatus) -> str:
    return {
        ProviderStatus.LOADING: "...",
        ProviderStatus.NO_CREDENTIALS: "sign in",
        ProviderStatus.EXPIRED: "expired",
        ProviderStatus.ERROR: "error",
    }.get(status, "—")
