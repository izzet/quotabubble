from __future__ import annotations

import json
import logging
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel

from quotabubble.utils import write_text_atomic

CONFIG_DIR = Path(user_config_dir("quotabubble", appauthor=False))
logger = logging.getLogger(__name__)


def default_settings_path() -> Path:
    return CONFIG_DIR / "settings.json"


def parse_thresholds(value: str | list[int] | None) -> list[int]:
    if value is None:
        return [75, 90]
    if isinstance(value, list):
        parsed = [int(v) for v in value if 1 <= int(v) <= 100]
        return sorted(set(parsed))

    parts = [p.strip() for p in value.replace(",", " ").split()]
    thresholds = set()
    for part in parts:
        try:
            val = int(part)
        except ValueError:
            raise ValueError(
                f"Invalid threshold '{part}': must be an integer between 1 and 100"
            ) from None
        if not (1 <= val <= 100):
            raise ValueError(f"Invalid threshold '{part}': must be between 1 and 100")
        thresholds.add(val)
    return sorted(thresholds)


def format_thresholds(thresholds: list[int]) -> str:
    return ", ".join(str(t) for t in sorted(set(thresholds)))


class Settings(BaseModel):
    idle_opacity: float = 0.25
    hover_opacity: float = 1.0
    fade_delay_ms: int = 700
    fade_duration_ms: int = 180
    show_remaining: bool = False
    launch_at_login: bool = False
    refresh_interval_ms: int = 300_000
    enabled_providers: list[str] | None = None
    # Fallback only: populated when the OS keyring is unavailable at save time.
    api_keys: dict[str, str] = {}
    position: tuple[int, int] | None = None
    notify_usage: bool = True
    notify_status: bool = True
    thresholds: list[int] = [75, 90]
    provider_thresholds: dict[str, list[int]] = {}

    def effective_thresholds(self, provider_id: str) -> list[int]:
        return self.provider_thresholds.get(provider_id, self.thresholds)

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        target = path or default_settings_path()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        try:
            settings = cls.model_validate(raw)
        except ValueError:
            logger.warning("settings at %s are invalid; using defaults", target)
            return cls()
        logger.info(
            "settings loaded from %s (providers=%s, keys=%d)",
            target,
            settings.enabled_providers,
            len(settings.api_keys),
        )
        return settings

    def save(self, path: Path | None = None) -> None:
        target = path or default_settings_path()
        write_text_atomic(target, self.model_dump_json(indent=2))
        logger.info(
            "settings saved to %s (providers=%s, keys=%d)",
            target,
            self.enabled_providers,
            len(self.api_keys),
        )
