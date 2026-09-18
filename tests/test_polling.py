from __future__ import annotations

import time

import pytest

from quotabubble.app.polling import (
    ERROR_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    PollingWorker,
)
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow


@pytest.fixture(autouse=True)
def _isolate_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("quotabubble.app.polling.load_snapshots", lambda: {})
    monkeypatch.setattr("quotabubble.app.polling.save_snapshots", lambda *args, **kwargs: None)


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
    assert received[0].fetched_at is not None
    assert received[1].status is ProviderStatus.OK
    assert received[1].stale is True
    assert received[1].fetched_at == received[0].fetched_at


def test_error_without_last_good_is_emitted(qapp: object) -> None:
    worker = PollingWorker([_SequencedProvider("claude", [_error()])], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert received[0].status is ProviderStatus.ERROR
    assert received[0].stale is False


def test_error_backs_off_the_provider(qapp: object) -> None:
    worker = PollingWorker([_SequencedProvider("claude", [_error(), _ok()])], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()
    worker.poll()

    assert len(received) == 1
    assert received[0].status is ProviderStatus.ERROR


def test_force_poll_bypasses_backoff(qapp: object) -> None:
    worker = PollingWorker([_SequencedProvider("claude", [_error(), _ok()])], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()
    assert len(received) == 1
    assert received[0].status is ProviderStatus.ERROR

    # Regular poll does not run due to backoff
    worker.poll()
    assert len(received) == 1

    # Force poll bypasses backoff
    worker.poll(force=True)
    assert len(received) == 2
    assert received[1].status is ProviderStatus.OK


class _RaisingProvider:
    uses_api_key = False

    def __init__(self, provider_id: str) -> None:
        self.id = provider_id
        self.display_name = provider_id.title()

    def detect(self) -> bool:
        return True

    def fetch(self) -> UsageSnapshot:
        raise RuntimeError("boom")


def test_fetch_exception_is_converted_to_error_snapshot(qapp: object) -> None:
    worker = PollingWorker([_RaisingProvider("claude")], 60000)
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert len(received) == 1
    assert received[0].status is ProviderStatus.ERROR
    assert received[0].message == "unexpected error"


def test_fetch_exception_does_not_abort_remaining_providers(qapp: object) -> None:
    worker = PollingWorker(
        [_RaisingProvider("claude"), _FakeProvider("codex")], 60000
    )
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()

    assert [snapshot.provider for snapshot in received] == ["claude", "codex"]
    assert received[0].status is ProviderStatus.ERROR
    assert received[1].status is ProviderStatus.OK


def _error_with_retry_after(seconds: float) -> UsageSnapshot:
    return UsageSnapshot(
        provider="claude",
        display_name="Claude",
        status=ProviderStatus.ERROR,
        message="HTTP 429",
        retry_after=seconds,
    )


def test_tiny_retry_after_is_clamped_to_minimum_backoff(qapp: object) -> None:
    worker = PollingWorker(
        [_SequencedProvider("claude", [_error_with_retry_after(1.0), _ok()])], 60000
    )
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    before = time.monotonic()
    worker.poll()

    # A retry_after (1s) far below ERROR_BACKOFF_SECONDS (300s) is still
    # floored to the minimum backoff.
    assert worker._retry_at["claude"] >= before + ERROR_BACKOFF_SECONDS

    # The next regular poll must therefore not bypass backoff.
    worker.poll()
    assert len(received) == 1


def test_huge_retry_after_is_clamped_to_maximum_backoff(qapp: object) -> None:
    worker = PollingWorker(
        [_SequencedProvider("claude", [_error_with_retry_after(999_999.0)])], 60000
    )
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    before = time.monotonic()
    worker.poll()

    delay = worker._retry_at["claude"]
    # retry_at is monotonic-clock-relative; assert it doesn't exceed now + MAX_BACKOFF.
    assert delay <= before + MAX_BACKOFF_SECONDS + 1.0
    assert delay > before + ERROR_BACKOFF_SECONDS


def test_no_credentials_status_clears_prior_backoff(qapp: object) -> None:
    worker = PollingWorker(
        [
            _SequencedProvider(
                "claude",
                [
                    _error(),
                    UsageSnapshot(
                        provider="claude",
                        display_name="Claude",
                        status=ProviderStatus.NO_CREDENTIALS,
                    ),
                ],
            )
        ],
        60000,
    )
    received: list[UsageSnapshot] = []
    worker.snapshot_ready.connect(received.append)

    worker.poll()
    assert worker._retry_at
    assert worker._failures

    # Force to bypass the backoff so the NO_CREDENTIALS result is observed.
    worker.poll(force=True)

    assert received[-1].status is ProviderStatus.NO_CREDENTIALS
    assert "claude" not in worker._retry_at
    assert "claude" not in worker._failures
