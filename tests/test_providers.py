from __future__ import annotations

from quotabubble.app.providers import loading_snapshot, select_providers
from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot


class _FakeProvider:
    def __init__(self, provider_id: str, detected: bool) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()
        self._detected = detected

    def detect(self) -> bool:
        return self._detected

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_select_defaults_to_detected_providers() -> None:
    providers = [_FakeProvider("claude", True), _FakeProvider("codex", False)]

    selected = select_providers(providers, Settings())

    assert [provider.id for provider in selected] == ["claude"]


def test_select_respects_explicit_selection() -> None:
    providers = [_FakeProvider("claude", True), _FakeProvider("codex", False)]

    selected = select_providers(providers, Settings(enabled_providers=["codex"]))

    assert [provider.id for provider in selected] == ["codex"]


def test_loading_snapshot_marks_loading() -> None:
    snapshot = loading_snapshot(_FakeProvider("claude", True))

    assert snapshot.provider == "claude"
    assert snapshot.status is ProviderStatus.LOADING
