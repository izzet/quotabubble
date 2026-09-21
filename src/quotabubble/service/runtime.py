from __future__ import annotations

from quotabubble.app.cache import load_snapshots
from quotabubble.app.providers import build_providers, merge_selected_snapshots, select_providers
from quotabubble.app.runtime import PollingRuntime
from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.presentation.builder import build_bubble_view
from quotabubble.providers.base import Provider, UsageSnapshot


class ServiceRuntime:
    """The Qt-free application state exposed to desktop frontends."""

    def __init__(
        self,
        settings: Settings,
        *,
        providers: list[Provider] | None = None,
        cached: dict[str, UsageSnapshot] | None = None,
    ) -> None:
        self._settings = settings
        candidates = build_providers(settings) if providers is None else providers
        self._providers = select_providers(candidates, settings)
        self._cached = load_snapshots() if cached is None else cached
        self._state = AppState()
        self._state.replace(merge_selected_snapshots(self._providers, [], self._cached))
        self._polling = PollingRuntime(self._providers, last_good=self._cached)

    @property
    def refresh_interval_seconds(self) -> float:
        return self._settings.refresh_interval_ms / 1000

    def refresh(self, *, force: bool = False) -> list[UsageSnapshot]:
        snapshots = self._polling.poll(force=force)
        for snapshot in snapshots:
            self._state.update(snapshot)
        return snapshots

    def state_json(self) -> str:
        return build_bubble_view(self._state.ordered(), self._settings).model_dump_json()
