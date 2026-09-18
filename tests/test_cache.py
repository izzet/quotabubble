from __future__ import annotations

import json
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


def test_load_non_dict_top_level_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "last_good.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert load_snapshots(path) == {}


def test_load_skips_corrupted_entries_but_keeps_valid_ones(tmp_path: Path) -> None:
    path = tmp_path / "last_good.json"
    good = UsageSnapshot(
        provider="claude",
        display_name="Claude",
        windows=[UsageWindow(label="5h", used_pct=10.0)],
    )
    save_snapshots({"claude": good}, path)

    # Corrupt one entry in-place while leaving the other valid.
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["codex"] = {"provider": "codex"}  # missing required display_name
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_snapshots(path)

    assert "claude" in loaded
    assert loaded["claude"].windows[0].used_pct == 10.0
    assert "codex" not in loaded
