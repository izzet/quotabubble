from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from quotabubble.app.cache import CACHE_DIR
from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow

logger = logging.getLogger(__name__)

NOTIFICATIONS_CACHE_FILE = CACHE_DIR / "notifications.json"


# A new reset cycle must advance resets_at by at least 3 minutes (180 seconds)
# to ignore sub-second server timestamp jitter and 00:59:59 / 01:00:00 rounding differences.
RESET_ADVANCE_MINIMUM_SECONDS = 180


def _has_resets_at_advanced(new_dt: datetime | None, old_iso: str | None) -> bool:
    if new_dt is None or old_iso is None:
        return False
    try:
        old_dt = datetime.fromisoformat(old_iso)
    except (ValueError, TypeError):
        return False
    if new_dt.tzinfo is None and old_dt.tzinfo is not None:
        new_dt = new_dt.replace(tzinfo=UTC)
    elif new_dt.tzinfo is not None and old_dt.tzinfo is None:
        old_dt = old_dt.replace(tzinfo=UTC)
    return (new_dt - old_dt).total_seconds() > RESET_ADVANCE_MINIMUM_SECONDS


class WindowNotificationState(BaseModel):
    last_resets_at: str | None = None
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
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(state.model_dump_json(indent=2), encoding="utf-8")


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

        windows = list(snapshot.windows)
        if not windows and snapshot.credits and snapshot.credits.used_pct is not None:
            windows.append(
                UsageWindow(
                    label="Credits",
                    key="credits",
                    used_pct=snapshot.credits.used_pct,
                )
            )

        thresholds = self._settings.effective_thresholds(provider_id)
        for window in windows:
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
        cycle_reset = _has_resets_at_advanced(
            window.resets_at, win_state.last_resets_at
        )
        if not cycle_reset and win_state.last_used_pct is not None:
            if window.used_pct < win_state.last_used_pct - 15.0:
                cycle_reset = True

        if win_state.depleted_notified and window.used_pct < 100.0:
            if self._settings.notify_status:
                pct = round(window.used_pct)
                msg = f"{snapshot.display_name} ({window.label}): quota recovered ({pct}% used)"
                self.notify.emit(
                    f"QuotaBubble — {snapshot.display_name}",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                )
            win_state.depleted_notified = False

        # A threshold only re-arms if usage drops below it.
        # Even across cycle resets, if usage has not dropped below a threshold, it must not re-fire.
        win_state.fired_thresholds = [
            t for t in win_state.fired_thresholds if t <= window.used_pct
        ]

        if window.used_pct >= 100.0:
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
                if window.used_pct >= t
                and t not in win_state.fired_thresholds
                and (win_state.last_used_pct is None or win_state.last_used_pct < t)
            ]
            if newly_crossed:
                highest = max(newly_crossed)
                icon = (
                    QSystemTrayIcon.MessageIcon.Warning
                    if highest >= 90
                    else QSystemTrayIcon.MessageIcon.Information
                )
                pct = round(window.used_pct)
                msg = f"{snapshot.display_name} ({window.label}): {pct}% quota used"
                self.notify.emit(
                    f"QuotaBubble — {snapshot.display_name}",
                    msg,
                    icon,
                )
                win_state.fired_thresholds.extend(newly_crossed)

        win_state.last_used_pct = window.used_pct
        if window.resets_at is not None:
            win_state.last_resets_at = window.resets_at.replace(microsecond=0).isoformat()

    def _persist(self) -> None:
        try:
            save_notification_state(self._state, self._state_path)
        except Exception:
            logger.exception("Failed to persist notification state")
