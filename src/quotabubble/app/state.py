from __future__ import annotations

from quotabubble.providers.base import UsageSnapshot


class AppState:
    def __init__(self) -> None:
        self._snapshots: list[UsageSnapshot] = []

    def update(self, snapshot: UsageSnapshot) -> None:
        for index, existing in enumerate(self._snapshots):
            if existing.provider == snapshot.provider:
                self._snapshots[index] = snapshot
                return
        self._snapshots.append(snapshot)

    def replace(self, snapshots: list[UsageSnapshot]) -> None:
        self._snapshots = list(snapshots)

    def ordered(self) -> list[UsageSnapshot]:
        return list(self._snapshots)
