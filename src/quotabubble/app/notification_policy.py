from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from quotabubble.app.cache import CACHE_DIR
from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow, snapshot_windows
from quotabubble.utils import write_text_atomic

logger = logging.getLogger(__name__)
NOTIFICATIONS_CACHE_FILE = CACHE_DIR / "notifications.json"


class WindowNotificationState(BaseModel):
    last_used_pct: float | None = None
    fired_thresholds: list[int] = Field(default_factory=list)
    depleted_notified: bool = False


class NotificationState(BaseModel):
    windows: dict[str, WindowNotificationState] = Field(default_factory=dict)
    provider_expired: dict[str, bool] = Field(default_factory=dict)


class NotificationEvent(BaseModel):
    title: str
    message: str
    urgency: Literal["normal", "critical"] = "normal"


def load_notification_state(path: Path | None = None) -> NotificationState:
    try:
        raw = json.loads((path or NOTIFICATIONS_CACHE_FILE).read_text(encoding="utf-8"))
        return (
            NotificationState.model_validate(raw) if isinstance(raw, dict) else NotificationState()
        )
    except (OSError, ValueError):
        return NotificationState()


def save_notification_state(state: NotificationState, path: Path | None = None) -> None:
    write_text_atomic(path or NOTIFICATIONS_CACHE_FILE, state.model_dump_json(indent=2))


class NotificationPolicy:
    def __init__(self, settings: Settings, path: Path | None = None) -> None:
        self._settings, self._path, self._state = settings, path, load_notification_state(path)

    def set_settings(self, settings: Settings) -> None:
        self._settings = settings

    def process_snapshot(self, snapshot: UsageSnapshot) -> list[NotificationEvent]:
        if snapshot.stale or snapshot.status is ProviderStatus.LOADING:
            return []
        events: list[NotificationEvent] = []
        title = f"QuotaBubble — {snapshot.display_name}"
        if snapshot.status is ProviderStatus.EXPIRED:
            if not self._state.provider_expired.get(snapshot.provider, False):
                if self._settings.notify_status:
                    events.append(
                        NotificationEvent(
                            title=title,
                            message=f"{snapshot.display_name}: quota depleted or rate limited",
                            urgency="critical",
                        )
                    )
                self._state.provider_expired[snapshot.provider] = True
                self._persist()
            return events
        if snapshot.status is not ProviderStatus.OK:
            return events
        if self._state.provider_expired.get(snapshot.provider, False):
            if self._settings.notify_status:
                events.append(
                    NotificationEvent(
                        title=title, message=f"{snapshot.display_name}: service recovered"
                    )
                )
            self._state.provider_expired[snapshot.provider] = False
        thresholds = self._settings.effective_thresholds(snapshot.provider)
        for window in snapshot_windows(snapshot):
            state = self._state.windows.setdefault(
                f"{snapshot.provider}:{window.key or window.label}", WindowNotificationState()
            )
            events.extend(self._process_window(snapshot, window, state, thresholds))
        self._persist()
        return events

    def _process_window(
        self,
        snapshot: UsageSnapshot,
        window: UsageWindow,
        state: WindowNotificationState,
        thresholds: list[int],
    ) -> list[NotificationEvent]:
        events: list[NotificationEvent] = []
        current, previous = window.used_pct, state.last_used_pct
        title = f"QuotaBubble — {snapshot.display_name}"
        if previous is not None and previous > 0 and current == 0:
            if self._settings.notify_status:
                events.append(
                    NotificationEvent(
                        title=title,
                        message=f"{snapshot.display_name} ({window.label}): quota reset (0% used)",
                    )
                )
            state.fired_thresholds.clear()
            state.depleted_notified = False
        elif state.depleted_notified and current < 100:
            if self._settings.notify_status:
                message = (
                    f"{snapshot.display_name} ({window.label}): quota recovered "
                    f"({round(current)}% used)"
                )
                events.append(
                    NotificationEvent(
                        title=title,
                        message=message,
                    )
                )
            state.depleted_notified = False
        state.fired_thresholds = [
            threshold for threshold in state.fired_thresholds if threshold <= current
        ]
        if current >= 100:
            if not state.depleted_notified:
                if self._settings.notify_status:
                    message = (
                        f"{snapshot.display_name} ({window.label}): quota depleted "
                        "(100% used)"
                    )
                    events.append(
                        NotificationEvent(
                            title=title,
                            message=message,
                            urgency="critical",
                        )
                    )
                state.depleted_notified = True
            state.fired_thresholds = sorted(set(state.fired_thresholds) | set(thresholds))
        elif self._settings.notify_usage:
            crossed = [
                threshold
                for threshold in sorted(thresholds)
                if current >= threshold
                and threshold not in state.fired_thresholds
                and (previous is None or previous < threshold)
            ]
            if crossed:
                highest = max(crossed)
                message = (
                    f"{snapshot.display_name} ({window.label}): "
                    f"{round(current)}% quota used"
                )
                events.append(
                    NotificationEvent(
                        title=title,
                        message=message,
                        urgency="critical" if highest >= 90 else "normal",
                    )
                )
                state.fired_thresholds.extend(crossed)
        state.last_used_pct = current
        return events

    def _persist(self) -> None:
        try:
            save_notification_state(self._state, self._path)
        except Exception:
            logger.exception("Failed to persist notification state")
