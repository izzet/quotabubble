from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from quotabubble.app.notification_policy import (
    NotificationEvent,
    NotificationPolicy,
    NotificationState,
    WindowNotificationState,
    load_notification_state,
    save_notification_state,
)
from quotabubble.app.settings import Settings
from quotabubble.providers.base import UsageSnapshot

__all__ = [
    "NotificationManager",
    "NotificationState",
    "WindowNotificationState",
    "load_notification_state",
    "save_notification_state",
]


class NotificationManager(QObject):
    notify = Signal(str, str, object)

    def __init__(
        self, settings: Settings, state_path: Path | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._policy = NotificationPolicy(settings, state_path)

    def set_settings(self, settings: Settings) -> None:
        self._policy.set_settings(settings)

    def send_test_notification(self) -> None:
        self._emit(
            NotificationEvent(
                title="QuotaBubble",
                message="Test notification: QuotaBubble alerts are configured properly.",
            )
        )

    def process_snapshot(self, snapshot: UsageSnapshot) -> None:
        for event in self._policy.process_snapshot(snapshot):
            self._emit(event)

    def _emit(self, event: NotificationEvent) -> None:
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if event.urgency == "critical"
            else QSystemTrayIcon.MessageIcon.Information
        )
        self.notify.emit(event.title, event.message, icon)
