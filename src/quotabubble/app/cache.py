from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_cache_dir

from quotabubble.providers.base import UsageSnapshot

CACHE_DIR = Path(user_cache_dir("quotabubble", appauthor=False))
LAST_GOOD_FILE = CACHE_DIR / "last_good.json"


def load_snapshots(path: Path | None = None) -> dict[str, UsageSnapshot]:
    target = path or LAST_GOOD_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    snapshots: dict[str, UsageSnapshot] = {}
    for provider_id, payload in raw.items():
        try:
            snapshots[provider_id] = UsageSnapshot.model_validate(payload)
        except ValueError:
            continue
    return snapshots


def save_snapshots(snapshots: dict[str, UsageSnapshot], path: Path | None = None) -> None:
    target = path or LAST_GOOD_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        provider_id: snapshot.model_dump(mode="json")
        for provider_id, snapshot in snapshots.items()
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
