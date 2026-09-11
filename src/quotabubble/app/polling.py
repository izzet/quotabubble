from __future__ import annotations

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot

from quotabubble.providers.base import Provider, UsageSnapshot

DEFAULT_REFRESH_INTERVAL_MS = 60_000


class PollingWorker(QObject):
    snapshot_ready = Signal(object)

    def __init__(
        self,
        providers: list[Provider],
        interval_ms: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._providers = providers
        self._interval_ms = interval_ms
        self._timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        self.poll()

    @Slot()
    def poll(self) -> None:
        for provider in self._providers:
            self.snapshot_ready.emit(provider.fetch())

    @Slot(int)
    def set_interval(self, interval_ms: int) -> None:
        self._interval_ms = interval_ms
        if self._timer is not None:
            self._timer.setInterval(interval_ms)

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


class PollingService(QObject):
    snapshot_ready = Signal(object)
    interval_changed = Signal(int)

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

    def start(self) -> None:
        self._thread.start()

    def set_interval(self, interval_ms: int) -> None:
        self.interval_changed.emit(interval_ms)

    @Slot(object)
    def _relay(self, snapshot: UsageSnapshot) -> None:
        self.snapshot_ready.emit(snapshot)

    def stop(self) -> None:
        QMetaObject.invokeMethod(self._worker, "stop", Qt.ConnectionType.QueuedConnection)
        self._thread.quit()
        self._thread.wait(2000)
