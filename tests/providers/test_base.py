from __future__ import annotations

from quotabubble.providers.base import format_plan, parse_retry_after


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
