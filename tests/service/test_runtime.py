from __future__ import annotations

import json

from quotabubble.app.settings import Settings
from quotabubble.providers.base import UsageSnapshot
from quotabubble.service.runtime import ServiceRuntime


class _Provider:
    uses_api_key = False

    def __init__(self) -> None:
        self.id = "codex"
        self.display_name = "Codex"

    def detect(self) -> bool:
        return True

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_service_runtime_seeds_and_serializes_selected_providers(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.runtime.save_snapshots", lambda snapshots: None)
    runtime = ServiceRuntime(Settings(), providers=[_Provider()], cached={})

    initial = json.loads(runtime.state_json())
    runtime.refresh(force=True)
    refreshed = json.loads(runtime.state_json())

    assert initial["version"] == 1
    assert initial["providers"][0]["name"] == "Codex"
    assert initial["providers"][0]["expanded_metrics"][0]["label"] == "..."
    assert refreshed["version"] == 1
    assert refreshed["providers"][0]["expanded_metrics"][0]["label"] == "—"


def test_service_runtime_reloads_saved_settings(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.runtime.save_snapshots", lambda snapshots: None)
    monkeypatch.setattr(
        "quotabubble.service.runtime.Settings.load",
        lambda: Settings(show_remaining=True, enabled_providers=[]),
    )
    runtime = ServiceRuntime(Settings(), providers=[_Provider()], cached={})

    runtime.reload_settings()

    state = json.loads(runtime.state_json())

    assert state["providers"] == []
    assert json.loads(runtime.appearance_json()) == state["appearance"]


def test_service_runtime_records_history(monkeypatch) -> None:
    monkeypatch.setattr("quotabubble.app.runtime.save_snapshots", lambda snapshots: None)
    recorded: list[UsageSnapshot] = []

    class Recorder:
        def __init__(self, settings: Settings) -> None:
            pass

        def record(self, snapshot: UsageSnapshot) -> None:
            recorded.append(snapshot)

    monkeypatch.setattr("quotabubble.service.runtime.HistoryRecorder", Recorder)
    runtime = ServiceRuntime(Settings(history_enabled=True), providers=[_Provider()], cached={})

    runtime.refresh(force=True)

    assert [snapshot.provider for snapshot in recorded] == ["codex"]
