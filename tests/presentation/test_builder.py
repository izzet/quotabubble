from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotabubble.app.settings import Settings
from quotabubble.presentation.builder import build_bubble_view
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow


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

    view = build_bubble_view([snapshot], Settings(), now=now)

    provider = view.providers[0]
    assert provider.name == "Codex"
    assert provider.trailing == "Plus"
    assert [metric.label for metric in provider.compact_metrics] == ["5h", "wk"]
    assert [metric.label for metric in provider.expanded_metrics] == ["5h", "Weekly"]
    assert [metric.percent for metric in provider.compact_metrics] == [65, 20]
    assert provider.compact_metrics[0].tone == "warning"
    assert provider.expanded_metrics[0].reset_text == "3h"


def test_build_bubble_view_formats_non_ok_status() -> None:
    snapshot = UsageSnapshot(
        provider="codex", display_name="Codex", status=ProviderStatus.NO_CREDENTIALS
    )

    view = build_bubble_view([snapshot], Settings())

    assert view.providers[0].expanded_metrics[0].label == "sign in"
    assert view.providers[0].expanded_metrics[0].detail is None


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
