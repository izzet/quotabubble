from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotabubble.app.settings import Settings
from quotabubble.presentation.builder import build_bubble_view
from quotabubble.providers.base import Credits, ProviderStatus, UsageSnapshot, UsageWindow


def test_build_bubble_view_prepares_compact_and_expanded_metrics() -> None:
    now = datetime(2026, 9, 20, 20, tzinfo=UTC)
    snapshot = UsageSnapshot(
        provider="codex",
        display_name="Codex",
        plan="Plus",
        windows=[
            UsageWindow(label="5h", short="5h", used_pct=65, resets_at=now + timedelta(hours=3)),
            UsageWindow(label="Weekly", short="wk", used_pct=20),
        ],
    )

    view = build_bubble_view(
        [snapshot],
        Settings(idle_opacity=0.4, hover_opacity=0.9, fade_delay_ms=800),
        now=now,
    )

    provider = view.providers[0]
    assert provider.name == "Codex"
    assert provider.trailing == "Plus"
    assert [metric.percent for metric in provider.compact_metrics] == [65, 20]
    assert provider.compact_metrics[1].label == "Weekly"
    assert provider.compact_metrics[1].compact_label == "wk"
    assert provider.compact_metrics[0].tone == "warning"
    assert provider.expanded_metrics[0].reset_text == "3h"
    assert view.appearance.idle_opacity == 0.4
    assert view.appearance.hover_opacity == 0.9
    assert view.appearance.fade_delay_ms == 800


def test_build_bubble_view_formats_non_ok_status() -> None:
    snapshot = UsageSnapshot(
        provider="codex", display_name="Codex", status=ProviderStatus.NO_CREDENTIALS
    )

    view = build_bubble_view([snapshot], Settings())

    assert view.providers[0].expanded_metrics[0].label == "sign in"
    assert view.providers[0].expanded_metrics[0].detail is None
    assert view.providers[0].compact_metrics[0].label == "sign in"


def test_build_bubble_view_preserves_stale_status_context_and_credits() -> None:
    now = datetime(2026, 9, 20, 20, tzinfo=UTC)
    snapshot = UsageSnapshot(
        provider="codex",
        display_name="Codex",
        status=ProviderStatus.EXPIRED,
        plan="Plus",
        stale=True,
        fetched_at=now - timedelta(minutes=5),
        credits=Credits(display="$4.20"),
    )

    view = build_bubble_view([snapshot], Settings(), now=now)

    provider = view.providers[0]
    assert provider.trailing == "Plus · 5m ago"
    assert [metric.label for metric in provider.compact_metrics] == ["expired"]
    assert [metric.label for metric in provider.expanded_metrics] == ["expired", "Credits"]
    assert provider.expanded_metrics[1].detail == "$4.20"


def test_build_bubble_view_keeps_empty_provider_marker_to_one_expanded_label() -> None:
    snapshot = UsageSnapshot(provider="codex", display_name="Codex")

    view = build_bubble_view([snapshot], Settings())

    assert view.providers[0].expanded_metrics[0].label == "—"
    assert view.providers[0].expanded_metrics[0].detail is None


def test_build_bubble_view_preserves_usage_severity_when_showing_remaining() -> None:
    snapshot = UsageSnapshot(
        provider="claude",
        display_name="Claude",
        windows=[UsageWindow(key="session", label="Session", used_pct=90)],
    )

    view = build_bubble_view([snapshot], Settings(show_remaining=True))

    metric = view.providers[0].compact_metrics[0]
    assert metric.percent == 10
    assert metric.tone == "critical"


def test_build_bubble_view_includes_saved_position() -> None:
    view = build_bubble_view([], Settings(position=(120, 340)))
    assert view.position == (120, 340)

    view_none = build_bubble_view([], Settings())
    assert view_none.position is None
