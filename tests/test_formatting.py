from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quotabubble.ui.formatting import format_age, format_reset

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


def test_format_reset_naive_datetime() -> None:
    naive = datetime(2026, 9, 11, 13, 0)

    assert format_reset(naive, NOW) == "1h"


def test_format_age_none() -> None:
    assert format_age(None) == "stale"


def test_format_age_just_now() -> None:
    assert format_age(NOW - timedelta(seconds=10), NOW) == "just now"
    assert format_age(NOW + timedelta(seconds=10), NOW) == "just now"


def test_format_age_minutes() -> None:
    assert format_age(NOW - timedelta(minutes=2), NOW) == "2m ago"
    assert format_age(NOW - timedelta(minutes=45), NOW) == "45m ago"


def test_format_age_hours() -> None:
    assert format_age(NOW - timedelta(hours=1), NOW) == "1h ago"
    assert format_age(NOW - timedelta(hours=3, minutes=12), NOW) == "3h ago"


def test_format_age_days() -> None:
    assert format_age(NOW - timedelta(days=2), NOW) == "2d ago"


def test_format_age_naive_datetime() -> None:
    naive = datetime(2026, 9, 11, 11, 58)
    assert format_age(naive, NOW) == "2m ago"
