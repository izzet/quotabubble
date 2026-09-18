from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotabubble.app.history import (
    HOT_WINDOW,
    RETENTION,
    HistoryRecorder,
    HistorySample,
    HistoryStore,
    HourlyBucket,
    _prune_buckets,
    _record_sample,
    _trim_hot_samples,
    _update_bucket,
    load_history,
    save_history,
)
from quotabubble.app.settings import Settings
from quotabubble.providers.base import Credits, ProviderStatus, UsageSnapshot, UsageWindow


def _dt(hour: int, minute: int = 0, *, day: int = 18) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=UTC)


# --- load/save -----------------------------------------------------------


def test_load_missing_returns_empty_store(tmp_path: Path) -> None:
    store = load_history(tmp_path / "absent.json")

    assert store.hot_samples == []
    assert store.buckets == []
    assert store.version == 1


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore()
    store.hot_samples.append(
        HistorySample(provider="claude", window_key="5h", used_pct=42.0, timestamp=_dt(9))
    )
    store.buckets.append(
        HourlyBucket(
            provider="claude",
            window_key="5h",
            hour_start=_dt(9),
            min_pct=10.0,
            max_pct=42.0,
            sum_pct=52.0,
            sample_count=2,
            last_pct=42.0,
        )
    )

    save_history(store, path)
    loaded = load_history(path)

    assert loaded.hot_samples[0].used_pct == 42.0
    assert loaded.buckets[0].avg_pct == 26.0


def test_load_non_dict_top_level_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert load_history(path).hot_samples == []


def test_load_corrupted_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert load_history(path).buckets == []


def test_load_invalid_schema_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"version": 1, "hot_samples": "not-a-list"}), encoding="utf-8")

    assert load_history(path).hot_samples == []


def test_load_version_mismatch_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    payload = {
        "version": 999,
        "hot_samples": [],
        "buckets": [
            {
                "provider": "claude",
                "window_key": "5h",
                "hour_start": "2026-09-18T09:00:00Z",
                "min_pct": 1.0,
                "max_pct": 1.0,
                "sum_pct": 1.0,
                "sample_count": 1,
                "last_pct": 1.0,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_history(path).buckets == []


def test_avg_pct_is_not_persisted(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    store = HistoryStore()
    store.buckets.append(
        HourlyBucket(
            provider="claude",
            window_key="5h",
            hour_start=_dt(9),
            min_pct=10.0,
            max_pct=20.0,
            sum_pct=30.0,
            sample_count=2,
            last_pct=20.0,
        )
    )
    save_history(store, path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "avg_pct" not in raw["buckets"][0]


# --- pure helpers ----------------------------------------------------------


def test_update_bucket_creates_then_accumulates() -> None:
    store = HistoryStore()

    _update_bucket(store, "claude", "5h", 10.0, _dt(9, 0))
    _update_bucket(store, "claude", "5h", 20.0, _dt(9, 30))

    assert len(store.buckets) == 1
    bucket = store.buckets[0]
    assert bucket.min_pct == 10.0
    assert bucket.max_pct == 20.0
    assert bucket.sample_count == 2
    assert bucket.avg_pct == 15.0
    assert bucket.last_pct == 20.0


def test_update_bucket_starts_a_new_bucket_on_hour_boundary() -> None:
    store = HistoryStore()

    _update_bucket(store, "claude", "5h", 10.0, _dt(9, 55))
    _update_bucket(store, "claude", "5h", 45.0, _dt(10, 0))

    assert len(store.buckets) == 2
    assert store.buckets[0].hour_start == _dt(9)
    assert store.buckets[1].hour_start == _dt(10)
    assert store.buckets[1].sample_count == 1


def test_update_bucket_keeps_series_independent() -> None:
    store = HistoryStore()

    _update_bucket(store, "claude", "5h", 10.0, _dt(9))
    _update_bucket(store, "claude", "weekly", 50.0, _dt(9))
    _update_bucket(store, "codex", "5h", 5.0, _dt(9))

    assert len(store.buckets) == 3


def test_trim_hot_samples_drops_entries_older_than_hot_window() -> None:
    store = HistoryStore()
    store.hot_samples = [
        HistorySample(provider="claude", window_key="5h", used_pct=1.0, timestamp=_dt(8)),
        HistorySample(provider="claude", window_key="5h", used_pct=2.0, timestamp=_dt(9, 30)),
    ]

    _trim_hot_samples(store, now=_dt(10))

    assert [s.used_pct for s in store.hot_samples] == [2.0]


def test_trim_hot_samples_keeps_entries_exactly_at_the_boundary() -> None:
    store = HistoryStore()
    now = _dt(10)
    store.hot_samples = [
        HistorySample(provider="claude", window_key="5h", used_pct=1.0, timestamp=now - HOT_WINDOW)
    ]

    _trim_hot_samples(store, now=now)

    assert len(store.hot_samples) == 1


def test_prune_buckets_drops_entries_older_than_retention() -> None:
    store = HistoryStore()
    now = _dt(0, day=20)
    store.buckets = [
        HourlyBucket(
            provider="claude",
            window_key="5h",
            hour_start=now - RETENTION - timedelta(hours=1),
            min_pct=1.0,
            max_pct=1.0,
            sum_pct=1.0,
            sample_count=1,
            last_pct=1.0,
        ),
        HourlyBucket(
            provider="claude",
            window_key="5h",
            hour_start=now - timedelta(days=1),
            min_pct=2.0,
            max_pct=2.0,
            sum_pct=2.0,
            sample_count=1,
            last_pct=2.0,
        ),
    ]

    _prune_buckets(store, now=now)

    assert len(store.buckets) == 1
    assert store.buckets[0].last_pct == 2.0


def test_record_sample_updates_both_tiers_together() -> None:
    store = HistoryStore()

    _record_sample(store, "claude", "5h", 42.0, _dt(9))

    assert len(store.hot_samples) == 1
    assert len(store.buckets) == 1
    assert store.buckets[0].avg_pct == 42.0


# --- HistoryRecorder ---------------------------------------------------


def _snapshot(
    used_pct: float = 50.0,
    *,
    status: ProviderStatus = ProviderStatus.OK,
    stale: bool = False,
    fetched_at: datetime | None = None,
    windows: list[UsageWindow] | None = None,
    credits: Credits | None = None,
) -> UsageSnapshot:
    return UsageSnapshot(
        provider="claude",
        display_name="Claude",
        status=status,
        stale=stale,
        fetched_at=fetched_at or _dt(9),
        windows=(
            windows
            if windows is not None
            else [UsageWindow(label="5h", key="5h", used_pct=used_pct)]
        ),
        credits=credits,
    )


def test_record_skips_when_history_disabled(tmp_path: Path) -> None:
    settings = Settings(history_enabled=False)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")

    recorder.record(_snapshot())

    assert recorder._store.hot_samples == []


def test_record_skips_stale_snapshot(tmp_path: Path) -> None:
    settings = Settings(history_enabled=True)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")

    recorder.record(_snapshot(stale=True))

    assert recorder._store.hot_samples == []


def test_record_skips_non_ok_status(tmp_path: Path) -> None:
    settings = Settings(history_enabled=True)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")

    recorder.record(_snapshot(status=ProviderStatus.ERROR))

    assert recorder._store.hot_samples == []


def test_record_appends_a_sample_per_window(tmp_path: Path) -> None:
    settings = Settings(history_enabled=True)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")
    windows = [
        UsageWindow(label="5h", key="5h", used_pct=40.0),
        UsageWindow(label="Weekly", key="weekly", used_pct=20.0),
    ]

    recorder.record(_snapshot(windows=windows))

    assert {s.window_key for s in recorder._store.hot_samples} == {"5h", "weekly"}


def test_record_synthesizes_credits_window(tmp_path: Path) -> None:
    settings = Settings(history_enabled=True)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")

    recorder.record(
        _snapshot(windows=[], credits=Credits(display="$5.00", used_pct=82.0))
    )

    assert len(recorder._store.hot_samples) == 1
    assert recorder._store.hot_samples[0].window_key == "credits"
    assert recorder._store.hot_samples[0].used_pct == 82.0


def test_record_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    settings = Settings(history_enabled=True)

    HistoryRecorder(settings, path).record(_snapshot(used_pct=33.0))

    reloaded = HistoryRecorder(settings, path)
    assert reloaded._store.hot_samples[0].used_pct == 33.0


def test_record_falls_back_to_now_when_fetched_at_missing(tmp_path: Path) -> None:
    settings = Settings(history_enabled=True)
    recorder = HistoryRecorder(settings, tmp_path / "history.json")
    snapshot = UsageSnapshot(
        provider="claude",
        display_name="Claude",
        fetched_at=None,
        windows=[UsageWindow(label="5h", key="5h", used_pct=10.0)],
    )

    recorder.record(snapshot)

    assert recorder._store.hot_samples[0].timestamp is not None
