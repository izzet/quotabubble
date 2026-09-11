from __future__ import annotations

from datetime import UTC, datetime

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3_600
SECONDS_PER_DAY = 86_400


def format_reset(resets_at: datetime | None, now: datetime | None = None) -> str | None:
    if resets_at is None:
        return None
    if now is None:
        now = datetime.now(tz=resets_at.tzinfo or UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=resets_at.tzinfo or UTC)

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
