from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quotabubble.providers.parsing import as_number, parse_timestamp


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
