from __future__ import annotations

from datetime import UTC, datetime

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3_600
SECONDS_PER_DAY = 86_400


def format_reset(resets_at: datetime | None, now: datetime | None = None) -> str | None:
    if resets_at is None:
        return None
    if resets_at.tzinfo is None:
        resets_at = resets_at.replace(tzinfo=UTC)
    if now is None:
        now = datetime.now(tz=UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    seconds = int((resets_at - now).total_seconds())
    if seconds <= 0:
        return "now"

    days, remainder = divmod(seconds, SECONDS_PER_DAY)
    hours, remainder = divmod(remainder, SECONDS_PER_HOUR)
    minutes = remainder // SECONDS_PER_MINUTE

    if days > 0:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def format_age(fetched_at: datetime | None, now: datetime | None = None) -> str:
    if fetched_at is None:
        return "stale"
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    if now is None:
        now = datetime.now(tz=UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    seconds = max(0, int((now - fetched_at).total_seconds()))
    if seconds < SECONDS_PER_MINUTE:
        return "just now"

    days, remainder = divmod(seconds, SECONDS_PER_DAY)
    hours, remainder = divmod(remainder, SECONDS_PER_HOUR)
    minutes = remainder // SECONDS_PER_MINUTE

    if days > 0:
        return f"{days}d ago"
    if hours > 0:
        return f"{hours}h ago"
    return f"{minutes}m ago"
