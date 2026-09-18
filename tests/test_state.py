from __future__ import annotations

from quotabubble.app.state import AppState
from quotabubble.providers.base import UsageSnapshot


def _snapshot(provider: str) -> UsageSnapshot:
    return UsageSnapshot(provider=provider, display_name=provider.title())


def test_update_appends_new_provider() -> None:
    state = AppState()

    state.update(_snapshot("claude"))

    assert [s.provider for s in state.ordered()] == ["claude"]


def test_update_replaces_existing_provider_in_place() -> None:
    state = AppState()
    state.update(_snapshot("claude"))
    state.update(_snapshot("codex"))

    updated = _snapshot("claude").model_copy(update={"message": "refreshed"})
    state.update(updated)

    ordered = state.ordered()
    assert [s.provider for s in ordered] == ["claude", "codex"]
    assert ordered[0].message == "refreshed"


def test_replace_swaps_entire_list() -> None:
    state = AppState()
    state.update(_snapshot("claude"))

    state.replace([_snapshot("codex"), _snapshot("cursor")])

    assert [s.provider for s in state.ordered()] == ["codex", "cursor"]


def test_ordered_returns_a_copy_not_a_reference() -> None:
    state = AppState()
    state.update(_snapshot("claude"))

    snapshot_list = state.ordered()
    snapshot_list.append(_snapshot("codex"))

    assert [s.provider for s in state.ordered()] == ["claude"]
