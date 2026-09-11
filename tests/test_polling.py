from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication

from quotabubble.app.polling import PollingWorker
from quotabubble.providers.base import UsageSnapshot


@pytest.fixture(scope="module")
def qapp() -> Iterator[QCoreApplication]:
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeProvider:
    def __init__(self, provider_id: str) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()

    def fetch(self) -> UsageSnapshot:
        return UsageSnapshot(provider=self.id, display_name=self.display_name)


def test_poll_emits_a_snapshot_per_provider(qapp: QCoreApplication) -> None:
    worker = PollingWorker([_FakeProvider("claude"), _FakeProvider("codex")], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert [snapshot.provider for snapshot in received] == ["claude", "codex"]
