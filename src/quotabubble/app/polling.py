from __future__ import annotations

import logging
import time

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot

from quotabubble.providers.base import Provider, ProviderStatus, UsageSnapshot

DEFAULT_REFRESH_INTERVAL_MS = 60_000
ERROR_BACKOFF_SECONDS = 120.0
MAX_BACKOFF_SECONDS = 900.0
logger = logging.getLogger(__name__)


class PollingWorker(QObject):
    snapshot_ready = Signal(object)

    def __init__(
        self,
        providers: list[Provider],
        interval_ms: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._providers = list(providers)
        self._interval_ms = interval_ms
        self._timer: QTimer | None = None
        self._last_good: dict[str, UsageSnapshot] = {}
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}

    @Slot()
    def start(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        self.poll()

    @Slot()
    def poll(self) -> None:
        now = time.monotonic()
        for provider in self._providers:
            if now < self._retry_at.get(provider.id, 0.0):
                continue
            try:
                fresh = provider.fetch()
            except Exception:
                logger.exception("provider '%s' raised during fetch", provider.id)
                fresh = UsageSnapshot(
                    provider=provider.id,
                    display_name=provider.display_name,
                    status=ProviderStatus.ERROR,
                    message="unexpected error",
                )
            self._publish(fresh)

    def _publish(self, fresh: UsageSnapshot) -> None:
        provider_id = fresh.provider
        if fresh.status is ProviderStatus.OK:
            self._failures.pop(provider_id, None)
            self._retry_at.pop(provider_id, None)
            self._last_good[provider_id] = fresh
            logger.info("provider '%s' ok (%d windows)", provider_id, len(fresh.windows))
            self.snapshot_ready.emit(fresh)
            return
        if fresh.status is ProviderStatus.ERROR:
            failures = self._failures.get(provider_id, 0) + 1
            self._failures[provider_id] = failures
            delay = min(ERROR_BACKOFF_SECONDS * 2 ** (failures - 1), MAX_BACKOFF_SECONDS)
            self._retry_at[provider_id] = time.monotonic() + delay
            previous = self._last_good.get(provider_id)
            if previous is not None:
                logger.warning(
                    "provider '%s' error (%s); keeping last-good, retry in %.0fs",
                    provider_id,
                    fresh.message,
                    delay,
                )
                self.snapshot_ready.emit(previous.model_copy(update={"stale": True}))
            else:
                logger.warning("provider '%s' error (%s)", provider_id, fresh.message)
                self.snapshot_ready.emit(fresh)
            return
        self._failures.pop(provider_id, None)
        self._retry_at.pop(provider_id, None)
        logger.warning("provider '%s' %s (%s)", provider_id, fresh.status, fresh.message)
        self.snapshot_ready.emit(fresh)

    @Slot(object)
    def set_providers(self, providers: list[Provider]) -> None:
        changed = [provider.id for provider in providers] != [
            provider.id for provider in self._providers
        ]
        self._providers = list(providers)
        if changed:
            self.poll()

    @Slot(int)
    def set_interval(self, interval_ms: int) -> None:
        self._interval_ms = interval_ms
        if self._timer is not None:
            self._timer.setInterval(interval_ms)

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer.setParent(None)
            self._timer = None


class PollingService(QObject):
    snapshot_ready = Signal(object)
    interval_changed = Signal(int)
    providers_changed = Signal(object)

    def __init__(
        self,
        providers: list[Provider],
        interval_ms: int = DEFAULT_REFRESH_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._worker = PollingWorker(providers, interval_ms)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.snapshot_ready.connect(self._relay)
        self.interval_changed.connect(self._worker.set_interval)
        self.providers_changed.connect(self._worker.set_providers)

    def start(self) -> None:
        self._thread.start()

    def set_interval(self, interval_ms: int) -> None:
        self.interval_changed.emit(interval_ms)

    def set_providers(self, providers: list[Provider]) -> None:
        self.providers_changed.emit(list(providers))

    @Slot(object)
    def _relay(self, snapshot: UsageSnapshot) -> None:
        self.snapshot_ready.emit(snapshot)

    def stop(self) -> None:
        if not self._thread.isRunning():
            return
        QMetaObject.invokeMethod(
            self._worker, "stop", Qt.ConnectionType.BlockingQueuedConnection
        )
        self._thread.quit()
        self._thread.wait()
