from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from quotabubble.ui.icon import app_icon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: QWidget) -> None:
        super().__init__(app_icon(), window)
        self._window = window
        self.setToolTip("QuotaBubble")

        menu = QMenu()
        toggle_action = QAction("Show / Hide", menu)
        toggle_action.triggered.connect(self._toggle_window)
        menu.addAction(toggle_action)
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
