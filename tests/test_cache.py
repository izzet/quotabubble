from __future__ import annotations

from pathlib import Path

from quotabubble.app.cache import load_snapshots, save_snapshots
from quotabubble.providers.base import UsageSnapshot, UsageWindow


def test_cache_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "last_good.json"
    snapshot = UsageSnapshot(
        provider="claude",
        display_name="Claude",
        windows=[UsageWindow(label="5h", used_pct=10.0)],
    )

    save_snapshots({"claude": snapshot}, path)
    loaded = load_snapshots(path)

    assert loaded["claude"].windows[0].used_pct == 10.0


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    assert load_snapshots(tmp_path / "absent.json") == {}
