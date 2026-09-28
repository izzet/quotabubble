from __future__ import annotations

from datetime import UTC, datetime

from quotabubble.app.runtime import PollingRuntime
from quotabubble.providers.base import ProviderStatus, UsageSnapshot


class _Provider:
    uses_api_key = False

    def __init__(self, results: list[UsageSnapshot]) -> None:
        self.id = "codex"
        self.display_name = "Codex"
        self._results = results

    def detect(self) -> bool:
        return True

    def fetch(self) -> UsageSnapshot:
        return self._results.pop(0)


def test_runtime_stores_last_good_and_marks_it_stale_after_an_error() -> None:
    ok = UsageSnapshot(provider="codex", display_name="Codex")
    error = UsageSnapshot(
        provider="codex",
        display_name="Codex",
        status=ProviderStatus.ERROR,
        message="offline",
    )
    saved: list[dict[str, UsageSnapshot]] = []
    runtime = PollingRuntime(
        [_Provider([ok, error])],
        last_good={},
        save_last_good=lambda snapshots: saved.append(snapshots),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    first = runtime.poll()
    second = runtime.poll(force=True)

    assert first[0].fetched_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert second[0].stale is True
    assert saved == [{"codex": first[0]}]


def test_runtime_skips_unchanged_provider_selection() -> None:
    provider = _Provider([])
    runtime = PollingRuntime([provider], last_good={})

    assert runtime.set_providers([provider]) is False
