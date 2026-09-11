from __future__ import annotations

from quotabubble.app.polling import PollingWorker
from quotabubble.providers.base import UsageSnapshot


class _FakeProvider:
    def __init__(self, provider_id: str) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_poll_emits_a_snapshot_per_provider(qapp: object) -> None:
    worker = PollingWorker([_FakeProvider("claude"), _FakeProvider("codex")], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert [snapshot.provider for snapshot in received] == ["claude", "codex"]
