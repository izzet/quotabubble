from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.providers.base import UsageSnapshot, UsageWindow
from quotabubble.ui.bubble import BubbleWindow


def _state() -> AppState:
    state = AppState()
    state.update(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            windows=[
                UsageWindow(key="session", label="5h", used_pct=10.0),
                UsageWindow(key="weekly", label="Weekly", used_pct=20.0),
            ],
        )
    )
    return state


def _mouse_event(event_type: QEvent.Type, global_pos: QPointF) -> QMouseEvent:
    buttons = Qt.MouseButton.NoButton
    if event_type in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove):
        buttons = Qt.MouseButton.LeftButton
    return QMouseEvent(
        event_type,
        QPointF(0, 0),
        global_pos,
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_window_keeps_a_fixed_size(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(0, 0)))

    assert window.minimumSize() == window.maximumSize() == window.sizeHint()

    window.deleteLater()


def test_click_toggles_expansion(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(0, 0)))
    point = QPointF(window.x() + 10, window.y() + 10)

    window.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, point))
    window.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, point))
    assert window._expanded is True
    assert window._target_height() > window.minimumSize().height()

    window.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, point))
    window.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, point))
    assert window._expanded is False

    window.deleteLater()


def test_drag_moves_the_window_without_expanding(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(100, 100)))
    start = QPointF(window.x() + 10, window.y() + 10)
    window.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, start))

    first = QPointF(start.x() + 40, start.y() + 40)
    window.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, first))
    assert window._dragging is True
    x_after_first = window.x()

    second = QPointF(start.x() + 80, start.y() + 80)
    window.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, second))
    assert window.x() > x_after_first

    window.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, second))
    assert window._expanded is False
    assert window._dragging is False

    window.deleteLater()
