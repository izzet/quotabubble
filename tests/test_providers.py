from __future__ import annotations

from quotabubble.app.providers import (
    build_providers,
    loading_snapshot,
    merge_selected_snapshots,
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


def test_explicit_selection_initializes_selected_provider_credentials() -> None:
    provider = _FakeProvider("claude", True)
    calls = 0

    def detect() -> bool:
        nonlocal calls
        calls += 1
        return True

    provider.detect = detect

    assert select_providers([provider], Settings(enabled_providers=["claude"])) == [provider]
    assert calls == 1


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


def test_merge_selected_snapshots_seeds_new_provider_with_loading_when_no_cache() -> None:
    provider = _FakeProvider("claude", True)

    result = merge_selected_snapshots([provider], current=[], cached={})

    assert len(result) == 1
    assert result[0].provider == "claude"
    assert result[0].status is ProviderStatus.LOADING


def test_merge_selected_snapshots_seeds_new_provider_from_cache_as_stale() -> None:
    provider = _FakeProvider("claude", True)
    cached_snapshot = UsageSnapshot(provider="claude", display_name="Claude", stale=False)

    result = merge_selected_snapshots([provider], current=[], cached={"claude": cached_snapshot})

    assert len(result) == 1
    assert result[0].provider == "claude"
    assert result[0].stale is True


def test_merge_selected_snapshots_keeps_currently_displayed_value_untouched() -> None:
    provider = _FakeProvider("claude", True)
    live_snapshot = UsageSnapshot(provider="claude", display_name="Claude", stale=False)
    # A cache entry also exists, but the currently-displayed live value must win
    # -- this is the whole point of the merge: refresh must not flash live
    # data back to stale just because detection ran again.
    cached_snapshot = UsageSnapshot(provider="claude", display_name="Claude", stale=True)

    result = merge_selected_snapshots(
        [provider], current=[live_snapshot], cached={"claude": cached_snapshot}
    )

    assert result == [live_snapshot]


def test_merge_selected_snapshots_drops_providers_no_longer_selected() -> None:
    stale_entry = UsageSnapshot(provider="codex", display_name="Codex")

    result = merge_selected_snapshots([], current=[stale_entry], cached={})

    assert result == []


def test_merge_selected_snapshots_preserves_selected_order() -> None:
    claude = _FakeProvider("claude", True)
    codex = _FakeProvider("codex", True)
    codex_live = UsageSnapshot(provider="codex", display_name="Codex")

    result = merge_selected_snapshots([codex, claude], current=[codex_live], cached={})

    assert [snapshot.provider for snapshot in result] == ["codex", "claude"]


def test_merge_selected_snapshots_mixed_scenario() -> None:
    # claude: already displayed, must stay untouched
    # codex: newly selected, has a last-good cache entry -> stale placeholder
    # cursor: newly selected, no cache -> loading placeholder
    # deepseek: was displayed but is no longer selected -> dropped
    claude_live = UsageSnapshot(provider="claude", display_name="Claude", stale=False)
    deepseek_live = UsageSnapshot(provider="deepseek", display_name="DeepSeek")
    codex_cached = UsageSnapshot(provider="codex", display_name="Codex", stale=False)

    selected = [
        _FakeProvider("claude", True),
        _FakeProvider("codex", True),
        _FakeProvider("cursor", True),
    ]
    result = merge_selected_snapshots(
        selected, current=[claude_live, deepseek_live], cached={"codex": codex_cached}
    )

    assert [snapshot.provider for snapshot in result] == ["claude", "codex", "cursor"]
    assert result[0] is claude_live
    assert result[1].stale is True
    assert result[2].status is ProviderStatus.LOADING
