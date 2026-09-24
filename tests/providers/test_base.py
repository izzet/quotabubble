from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quotabubble.providers.base import (
    Credits,
    UsageSnapshot,
    UsageWindow,
    as_number,
    format_plan,
    parse_retry_after,
    parse_timestamp,
    snapshot_windows,
)


def test_parse_retry_after_none_and_empty() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None


def test_parse_retry_after_valid_seconds() -> None:
    assert parse_retry_after("30") == 30.0
    assert parse_retry_after("12.5") == 12.5


def test_parse_retry_after_negative_is_clamped_to_zero() -> None:
    assert parse_retry_after("-10") == 0.0


def test_parse_retry_after_non_numeric_returns_none() -> None:
    assert parse_retry_after("not-a-number") is None
    assert parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None


def test_format_plan_none_and_empty() -> None:
    assert format_plan(None) is None
    assert format_plan("") is None


def test_format_plan_normalizes_underscores_and_case() -> None:
    assert format_plan("max_20x") == "Max 20X"
    assert format_plan("pro") == "Pro"


def _snapshot(**overrides: object) -> UsageSnapshot:
    defaults: dict[str, object] = {"provider": "claude", "display_name": "Claude"}
    defaults.update(overrides)
    return UsageSnapshot(**defaults)


def test_snapshot_windows_returns_real_windows_as_is() -> None:
    windows = [UsageWindow(label="5h", key="5h", used_pct=42.0)]

    assert snapshot_windows(_snapshot(windows=windows)) == windows


def test_snapshot_windows_synthesizes_credits_when_no_windows() -> None:
    snapshot = _snapshot(windows=[], credits=Credits(display="$5.00", used_pct=82.0))

    windows = snapshot_windows(snapshot)

    assert len(windows) == 1
    assert windows[0].key == "credits"
    assert windows[0].used_pct == 82.0


def test_snapshot_windows_ignores_credits_without_used_pct() -> None:
    snapshot = _snapshot(windows=[], credits=Credits(display="$5.00"))

    assert snapshot_windows(snapshot) == []


def test_snapshot_windows_prefers_real_windows_over_credits() -> None:
    windows = [UsageWindow(label="5h", key="5h", used_pct=10.0)]
    snapshot = _snapshot(windows=windows, credits=Credits(display="$5.00", used_pct=82.0))

    assert snapshot_windows(snapshot) == windows


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3, 3.0), (2.5, 2.5), ("4.5", 4.5), (True, None), ("abc", None), (None, None), ([1], None)],
)
def test_as_number(value: object, expected: float | None) -> None:
    assert as_number(value) == expected


def test_parse_timestamp_reads_iso_strings() -> None:
    expected = datetime(2026, 9, 29, tzinfo=UTC)

    assert parse_timestamp("2026-09-29T00:00:00Z") == expected
    assert parse_timestamp("2026-09-29T00:00:00+00:00") == expected
    assert parse_timestamp("2026-09-29T00:00:00") == expected


def test_parse_timestamp_reads_epoch_seconds_and_milliseconds() -> None:
    expected = datetime.fromtimestamp(1_790_000_000, tz=UTC)

    assert parse_timestamp(1_790_000_000) == expected
    assert parse_timestamp(1_790_000_000_000) == expected
    assert parse_timestamp("1790000000") == expected


@pytest.mark.parametrize("value", ["", "not a date", None, True, [], {}])
def test_parse_timestamp_rejects_unusable_values(value: object) -> None:
    assert parse_timestamp(value) is None
