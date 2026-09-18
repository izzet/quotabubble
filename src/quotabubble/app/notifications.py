from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from quotabubble.app.cache import CACHE_DIR
from quotabubble.app.settings import Settings
from quotabubble.providers.base import (
    ProviderStatus,
    UsageSnapshot,
    UsageWindow,
    snapshot_windows,
)
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


def load_notification_state(path: Path | None = None) -> NotificationState:
    target = path or NOTIFICATIONS_CACHE_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return NotificationState()
    if not isinstance(raw, dict):
        return NotificationState()
    try:
        return NotificationState.model_validate(raw)
    except ValueError:
        return NotificationState()


def save_notification_state(state: NotificationState, path: Path | None = None) -> None:
    target = path or NOTIFICATIONS_CACHE_FILE
    write_text_atomic(target, state.model_dump_json(indent=2))


class NotificationManager(QObject):
    notify = Signal(str, str, object)  # title, message, QSystemTrayIcon.MessageIcon

    def __init__(
        self,
        settings: Settings,
        state_path: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._state_path = state_path
        self._state = load_notification_state(self._state_path)

    def set_settings(self, settings: Settings) -> None:
        self._settings = settings

    def send_test_notification(self) -> None:
        self.notify.emit(
            "QuotaBubble",
            "Test notification: QuotaBubble alerts are configured properly.",
            QSystemTrayIcon.MessageIcon.Information,
        )

    def process_snapshot(self, snapshot: UsageSnapshot) -> None:
        if snapshot.stale:
            return
        if snapshot.status == ProviderStatus.LOADING:
            return

        provider_id = snapshot.provider
        display_name = snapshot.display_name

        if snapshot.status == ProviderStatus.EXPIRED:
            was_expired = self._state.provider_expired.get(provider_id, False)
            if not was_expired:
                if self._settings.notify_status:
                    self.notify.emit(
                        f"QuotaBubble — {display_name}",
                        f"{display_name}: quota depleted or rate limited",
                        QSystemTrayIcon.MessageIcon.Warning,
                    )
                self._state.provider_expired[provider_id] = True
                self._persist()
            return
        elif snapshot.status == ProviderStatus.OK:
            was_expired = self._state.provider_expired.get(provider_id, False)
            if was_expired:
                if self._settings.notify_status:
                    self.notify.emit(
                        f"QuotaBubble — {display_name}",
                        f"{display_name}: service recovered",
                        QSystemTrayIcon.MessageIcon.Information,
                    )
                self._state.provider_expired[provider_id] = False
        else:
            return

        thresholds = self._settings.effective_thresholds(provider_id)
        for window in snapshot_windows(snapshot):
            window_key = window.key or window.label
            state_key = f"{provider_id}:{window_key}"
            win_state = self._state.windows.setdefault(
                state_key, WindowNotificationState()
            )
            self._process_window(snapshot, window, win_state, thresholds)

        self._persist()

    def _process_window(
        self,
        snapshot: UsageSnapshot,
        window: UsageWindow,
        win_state: WindowNotificationState,
        thresholds: list[int],
    ) -> None:
        current = window.used_pct
        prev = win_state.last_used_pct

        # Zeroed out alert: usage transitioned from >0 to 0%
        if prev is not None and prev > 0.0 and current == 0.0:
            if self._settings.notify_status:
                msg = f"{snapshot.display_name} ({window.label}): quota reset (0% used)"
                self.notify.emit(
                    f"QuotaBubble — {snapshot.display_name}",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                )
            win_state.fired_thresholds.clear()
            win_state.depleted_notified = False

        # Recovery from 100% depletion (when not zeroed out, e.g. dropped to 50%)
        elif win_state.depleted_notified and current < 100.0:
            if self._settings.notify_status:
                pct = round(current)
                msg = f"{snapshot.display_name} ({window.label}): quota recovered ({pct}% used)"
                self.notify.emit(
                    f"QuotaBubble — {snapshot.display_name}",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                )
            win_state.depleted_notified = False

        # Re-arm any threshold that current usage has dropped below
        win_state.fired_thresholds = [
            t for t in win_state.fired_thresholds if t <= current
        ]

        if current >= 100.0:
            if not win_state.depleted_notified:
                if self._settings.notify_status:
                    msg = f"{snapshot.display_name} ({window.label}): quota depleted (100% used)"
                    self.notify.emit(
                        f"QuotaBubble — {snapshot.display_name}",
                        msg,
                        QSystemTrayIcon.MessageIcon.Warning,
                    )
                win_state.depleted_notified = True
            for t in thresholds:
                if t not in win_state.fired_thresholds:
                    win_state.fired_thresholds.append(t)
        elif self._settings.notify_usage:
            newly_crossed = [
                t
                for t in sorted(thresholds)
                if current >= t
                and t not in win_state.fired_thresholds
                and (prev is None or prev < t)
            ]
            if newly_crossed:
                highest = max(newly_crossed)
                icon = (
                    QSystemTrayIcon.MessageIcon.Warning
                    if highest >= 90
                    else QSystemTrayIcon.MessageIcon.Information
                )
                pct = round(current)
                msg = f"{snapshot.display_name} ({window.label}): {pct}% quota used"
                self.notify.emit(
                    f"QuotaBubble — {snapshot.display_name}",
                    msg,
                    icon,
                )
                win_state.fired_thresholds.extend(newly_crossed)

        win_state.last_used_pct = current

    def _persist(self) -> None:
        try:
            save_notification_state(self._state, self._state_path)
        except Exception:
            logger.exception("Failed to persist notification state")
