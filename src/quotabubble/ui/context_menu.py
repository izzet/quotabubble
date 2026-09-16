from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget


def build_context_menu(
    parent: QWidget,
    on_settings: Callable[[], None],
    on_refresh: Callable[[], None] | None = None,
) -> QMenu:
    menu = QMenu(parent)
    if on_refresh is not None:
        refresh_action = QAction("Refresh", menu)
        refresh_action.triggered.connect(on_refresh)
        menu.addAction(refresh_action)
        menu.addSeparator()
    settings_action = QAction("Settings…", menu)
    settings_action.triggered.connect(on_settings)
    menu.addAction(settings_action)
    menu.addSeparator()
    quit_action = QAction("Quit QuotaBubble", menu)
    quit_action.triggered.connect(QApplication.quit)
    menu.addAction(quit_action)
    return menu
