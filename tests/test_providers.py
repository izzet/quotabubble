from __future__ import annotations

from quotabubble.app.providers import (
    build_providers,
    loading_snapshot,
    resolve_api_key,
    select_providers,
)
from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot


class _FakeProvider:
    uses_api_key = False

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


def test_resolve_api_key_prefers_keyring_over_settings_and_env(monkeypatch) -> None:
    monkeypatch.setattr(
        "quotabubble.app.providers.get_secret",
        lambda provider_id: "from-keyring" if provider_id == "deepseek" else None,
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    settings = Settings(api_keys={"deepseek": "from-settings"})

    assert resolve_api_key(settings, "deepseek") == "from-keyring"


def test_resolve_api_key_falls_back_to_settings_when_keyring_empty(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.providers.get_secret", lambda provider_id: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    settings = Settings(api_keys={"deepseek": "from-settings"})

    assert resolve_api_key(settings, "deepseek") == "from-settings"


def test_resolve_api_key_falls_back_to_environment(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.providers.get_secret", lambda provider_id: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")

    assert resolve_api_key(Settings(), "deepseek") == "from-env"


def test_build_providers_registers_all_expected_providers(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.providers.get_secret", lambda provider_id: None)
    providers = build_providers(Settings())
    assert [p.id for p in providers] == [
        "claude",
        "codex",
        "antigravity",
        "copilot",
        "cursor",
        "opencode",
        "deepseek",
        "openrouter",
    ]
