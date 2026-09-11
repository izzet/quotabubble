from __future__ import annotations

from quotabubble.app.polling import PollingWorker
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow


class _FakeProvider:
    uses_api_key = False

    def __init__(self, provider_id: str) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()

    def detect(self) -> bool:
        return True

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_poll_emits_a_snapshot_per_provider(qapp: object) -> None:
    worker = PollingWorker([_FakeProvider("claude"), _FakeProvider("codex")], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert [snapshot.provider for snapshot in received] == ["claude", "codex"]


def test_set_providers_swaps_and_repolls(qapp: object) -> None:
    worker = PollingWorker([_FakeProvider("claude")], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.set_providers([_FakeProvider("codex")])

    assert [snapshot.provider for snapshot in received] == ["codex"]


class _SequencedProvider:
    uses_api_key = False

    def __init__(self, provider_id: str, results: list[UsageSnapshot]) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()
        self._results = list(results)

    def detect(self) -> bool:
        return True

    def fetch(self) -> UsageSnapshot:
        return self._results.pop(0)


def _ok() -> UsageSnapshot:
    return UsageSnapshot(
        provider="claude",
        display_name="Claude",
        windows=[UsageWindow(label="5h", used_pct=10.0)],
    )


def _error() -> UsageSnapshot:
    return UsageSnapshot(
        provider="claude",
        display_name="Claude",
        status=ProviderStatus.ERROR,
        message="HTTP 429",
    )


def test_transient_error_keeps_the_last_good_snapshot(qapp: object) -> None:
    worker = PollingWorker([_SequencedProvider("claude", [_ok(), _error()])], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()
    worker.poll()

    assert received[0].status is ProviderStatus.OK
    assert received[0].stale is False
    assert received[1].status is ProviderStatus.OK
    assert received[1].stale is True


def test_error_without_last_good_is_emitted(qapp: object) -> None:
    worker = PollingWorker([_SequencedProvider("claude", [_error()])], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert received[0].status is ProviderStatus.ERROR
    assert received[0].stale is False
