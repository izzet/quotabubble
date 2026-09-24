from __future__ import annotations

from datetime import UTC, datetime

_EPOCH_MILLIS_THRESHOLD = 1e11


def as_number(value: object) -> float | None:
    """Coerce a JSON int, float, or numeric string to a float (never a bool)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def parse_timestamp(value: object) -> datetime | None:
    """Parse an ISO 8601 string or an epoch in seconds or milliseconds to UTC."""
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    number = as_number(value)
    if number is None:
        return None
    seconds = number / 1000 if number > _EPOCH_MILLIS_THRESHOLD else number
    return datetime.fromtimestamp(seconds, tz=UTC)
