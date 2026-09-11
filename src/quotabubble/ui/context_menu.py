from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget


def build_context_menu(parent: QWidget, on_settings: Callable[[], None]) -> QMenu:
    menu = QMenu(parent)
    settings_action = QAction("Settings…", menu)
    settings_action.triggered.connect(on_settings)
    menu.addAction(settings_action)
    menu.addSeparator()
    quit_action = QAction("Quit QuotaBubble", menu)
    quit_action.triggered.connect(QApplication.quit)
    menu.addAction(quit_action)
    return menu
