from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from quotabubble.app.logging_setup import LOG_DIR
from quotabubble.ui.icon import app_icon


class TrayIcon(QSystemTrayIcon):
    settings_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, window: QWidget) -> None:
        super().__init__(app_icon(), window)
        self._window = window
        self.setToolTip("QuotaBubble")

        menu = QMenu()
        toggle_action = QAction("Show / Hide", menu)
        toggle_action.triggered.connect(self._toggle_window)
        menu.addAction(toggle_action)

        refresh_action = QAction("Refresh", menu)
        refresh_action.triggered.connect(self._request_refresh)
        menu.addAction(refresh_action)

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self._request_settings)
        menu.addAction(settings_action)

        logs_action = QAction("Open logs", menu)
        logs_action.triggered.connect(self._open_logs)
        menu.addAction(logs_action)

        menu.addSeparator()
        quit_action = QAction("Quit QuotaBubble", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)
        self._menu = menu

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()

    def _request_settings(self) -> None:
        self.settings_requested.emit()

    def _request_refresh(self) -> None:
        self.refresh_requested.emit()

    def _open_logs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))
