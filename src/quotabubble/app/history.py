from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from quotabubble.app.cache import CACHE_DIR
from quotabubble.app.settings import Settings
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, snapshot_windows
from quotabubble.utils import write_text_atomic

HISTORY_CACHE_FILE = CACHE_DIR / "history.json"
HOT_WINDOW = timedelta(hours=1)
RETENTION = timedelta(days=30)
_CURRENT_VERSION = 1


class HistorySample(BaseModel):
    provider: str
    window_key: str
    used_pct: float
    timestamp: datetime


class HourlyBucket(BaseModel):
    provider: str
    window_key: str
    hour_start: datetime
    min_pct: float
    max_pct: float
    sum_pct: float
    sample_count: int
    last_pct: float

    @property
    def avg_pct(self) -> float:
        return self.sum_pct / self.sample_count


class HistoryStore(BaseModel):
    version: int = _CURRENT_VERSION
    hot_samples: list[HistorySample] = Field(default_factory=list)
    buckets: list[HourlyBucket] = Field(default_factory=list)


def load_history(path: Path | None = None) -> HistoryStore:
    target = path or HISTORY_CACHE_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return HistoryStore()
    if not isinstance(raw, dict):
        return HistoryStore()
    try:
        store = HistoryStore.model_validate(raw)
    except ValueError:
        return HistoryStore()
    if store.version != _CURRENT_VERSION:
        return HistoryStore()
    return store


def save_history(store: HistoryStore, path: Path | None = None) -> None:
    target = path or HISTORY_CACHE_FILE
    # No indent=2 here (unlike settings/cache/notifications): this store is
    # rewritten on every poll and can hold thousands of rows at full
    # retention, so pretty-printing isn't worth the extra bytes written.
    write_text_atomic(target, store.model_dump_json())


def _trim_hot_samples(store: HistoryStore, *, now: datetime) -> None:
    cutoff = now - HOT_WINDOW
    store.hot_samples[:] = [s for s in store.hot_samples if s.timestamp >= cutoff]


def _update_bucket(
    store: HistoryStore, provider: str, window_key: str, used_pct: float, timestamp: datetime
) -> None:
    hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
    for bucket in store.buckets:
        if (
            bucket.provider == provider
            and bucket.window_key == window_key
            and bucket.hour_start == hour_start
        ):
            bucket.min_pct = min(bucket.min_pct, used_pct)
            bucket.max_pct = max(bucket.max_pct, used_pct)
            bucket.sum_pct += used_pct
            bucket.sample_count += 1
            bucket.last_pct = used_pct
            return
    store.buckets.append(
        HourlyBucket(
            provider=provider,
            window_key=window_key,
            hour_start=hour_start,
            min_pct=used_pct,
            max_pct=used_pct,
            sum_pct=used_pct,
            sample_count=1,
            last_pct=used_pct,
        )
    )


def _prune_buckets(store: HistoryStore, *, now: datetime) -> None:
    cutoff = now - RETENTION
    store.buckets[:] = [b for b in store.buckets if b.hour_start >= cutoff]


def _record_sample(
    store: HistoryStore, provider: str, window_key: str, used_pct: float, timestamp: datetime
) -> None:
    store.hot_samples.append(
        HistorySample(
            provider=provider, window_key=window_key, used_pct=used_pct, timestamp=timestamp
        )
    )
    _trim_hot_samples(store, now=timestamp)
    _update_bucket(store, provider, window_key, used_pct, timestamp)


class HistoryRecorder:
    def __init__(self, settings: Settings, path: Path | None = None) -> None:
        self._settings = settings
        self._path = path
        self._store = load_history(path)

    def record(self, snapshot: UsageSnapshot) -> None:
        if not self._settings.history_enabled:
            return
        if snapshot.stale or snapshot.status is not ProviderStatus.OK:
            return

        timestamp = snapshot.fetched_at or datetime.now(UTC)
        for window in snapshot_windows(snapshot):
            window_key = window.key or window.label
            _record_sample(self._store, snapshot.provider, window_key, window.used_pct, timestamp)

        _prune_buckets(self._store, now=timestamp)
        save_history(self._store, self._path)
