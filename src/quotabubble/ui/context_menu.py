from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget


def build_context_menu(parent: QWidget) -> QMenu:
    menu = QMenu(parent)
    quit_action = QAction("Quit QuotaBubble", menu)
    quit_action.triggered.connect(QApplication.quit)
    menu.addAction(quit_action)
    return menu
