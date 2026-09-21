from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow
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


def test_expansion_controls_tick_timer(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(0, 0)))
    assert window._tick_timer.isActive() is False

    window._toggle_expanded()
    assert window._expanded is True
    assert window._tick_timer.isActive() is True

    window._toggle_expanded()
    assert window._expanded is False
    assert window._tick_timer.isActive() is False

    window.deleteLater()


def test_request_refresh_emits_signal(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(0, 0)))
    emitted = []
    window.refresh_requested.connect(lambda: emitted.append(True))

    window._request_refresh()
    assert emitted == [True]

    window.deleteLater()


def test_build_context_menu_actions(qapp: object) -> None:
    from PySide6.QtWidgets import QWidget

    from quotabubble.ui.context_menu import build_context_menu

    parent = QWidget()
    refreshed = []
    settings_opened = []
    menu = build_context_menu(
        parent,
        on_settings=lambda: settings_opened.append(True),
        on_refresh=lambda: refreshed.append(True),
    )
    action_texts = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert action_texts == ["Refresh", "Settings…", "Quit QuotaBubble"]

    # Trigger actions
    actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
    actions["Refresh"].trigger()
    assert refreshed == [True]
    actions["Settings…"].trigger()
    assert settings_opened == [True]
    parent.deleteLater()


def test_paint_expanded_stale_snapshot(qapp: object) -> None:
    from datetime import UTC, datetime, timedelta

    from PySide6.QtGui import QPainter, QPixmap

    from quotabubble.presentation.builder import build_bubble_view
    from quotabubble.ui.panel import paint_expanded

    now = datetime.now(tz=UTC)
    stale_snapshot = UsageSnapshot(
        provider="claude",
        display_name="Claude",
        plan="Pro",
        stale=True,
        fetched_at=now - timedelta(minutes=5),
        windows=[UsageWindow(key="session", label="5h", used_pct=40.0)],
    )

    pixmap = QPixmap(300, 200)
    painter = QPainter(pixmap)
    view = build_bubble_view([stale_snapshot], Settings(), now=now)
    paint_expanded(painter, view.providers, 0, 300)
    painter.end()


def test_window_paints_the_shared_view_in_both_states(qapp: object) -> None:
    from PySide6.QtGui import QPixmap

    window = BubbleWindow(_state(), Settings(position=(0, 0)))
    compact = QPixmap(window.size())
    window.render(compact)

    window._toggle_expanded()
    expanded = QPixmap(window._target_size())
    window.render(expanded)

    assert compact.isNull() is False
    assert expanded.isNull() is False
    window.deleteLater()


def test_expanded_status_renders_without_detail_text(qapp: object) -> None:
    from PySide6.QtGui import QPixmap

    state = AppState()
    state.update(
        UsageSnapshot(
            provider="claude",
            display_name="Claude",
            status=ProviderStatus.EXPIRED,
        )
    )
    window = BubbleWindow(state, Settings(position=(0, 0)))
    window._expanded = True
    window.refresh()

    rendered = QPixmap(window.size())
    window.render(rendered)

    assert rendered.isNull() is False
    window.deleteLater()


def test_tray_icon_actions_and_refresh_signal(qapp: object) -> None:
    from PySide6.QtWidgets import QWidget

    from quotabubble.ui.tray import TrayIcon

    window = QWidget()
    tray = TrayIcon(window)
    emitted = []
    tray.refresh_requested.connect(lambda: emitted.append(True))
    tray._request_refresh()
    assert emitted == [True]

    menu = tray.contextMenu()
    action_texts = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert "Refresh" in action_texts
    assert "Settings…" in action_texts

    tray.deleteLater()
    window.deleteLater()


def test_macos_tray_click_does_not_toggle_window(qapp: object, monkeypatch) -> None:
    from PySide6.QtWidgets import QWidget

    from quotabubble.ui import tray as tray_module
    from quotabubble.ui.tray import TrayIcon

    window = QWidget()
    tray = TrayIcon(window)
    monkeypatch.setattr(tray_module.sys, "platform", "darwin")

    tray._on_activated(tray.ActivationReason.Trigger)

    assert window.isVisible() is False
    tray.deleteLater()
    window.deleteLater()
