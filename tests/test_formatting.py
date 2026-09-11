from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotabubble.ui.formatting import format_reset

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def test_format_reset_none() -> None:
    assert format_reset(None) is None


def test_format_reset_minutes() -> None:
    assert format_reset(NOW + timedelta(minutes=45), NOW) == "45m"


def test_format_reset_hours_and_minutes() -> None:
    assert format_reset(NOW + timedelta(hours=1, minutes=24), NOW) == "1h 24m"


def test_format_reset_days() -> None:
    assert format_reset(NOW + timedelta(days=2), NOW) == "2d"


def test_format_reset_in_the_past() -> None:
    assert format_reset(NOW - timedelta(seconds=1), NOW) == "now"
