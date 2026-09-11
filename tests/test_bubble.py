from __future__ import annotations

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
            windows=[UsageWindow(label="5h", used_pct=10.0)],
        )
    )
    return state


def test_window_keeps_a_fixed_size(qapp: object) -> None:
    window = BubbleWindow(_state(), Settings(position=(0, 0)))

    assert window.minimumSize() == window.maximumSize() == window.sizeHint()

    window.deleteLater()
