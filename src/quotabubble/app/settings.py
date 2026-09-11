from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel

CONFIG_DIR = Path(user_config_dir("quotabubble", appauthor=False))


def default_settings_path() -> Path:
    return CONFIG_DIR / "settings.json"


class Settings(BaseModel):
    idle_opacity: float = 0.25
    hover_opacity: float = 1.0
    fade_delay_ms: int = 700
    fade_duration_ms: int = 180
    show_remaining: bool = False
    refresh_interval_ms: int = 60_000
    enabled_providers: list[str] | None = None
    api_keys: dict[str, str] = {}
    position: tuple[int, int] | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        target = path or default_settings_path()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        try:
            return cls.model_validate(raw)
        except ValueError:
            return cls()

    def save(self, path: Path | None = None) -> None:
        target = path or default_settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2), encoding="utf-8")
