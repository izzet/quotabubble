from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

LOG_DIR = Path(user_log_dir("quotabubble", appauthor=False))
LOG_FILE = LOG_DIR / "quotabubble.log"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO, path: Path | None = None) -> Path:
    target = path or LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    resolved = str(target)
    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler) and handler.baseFilename == resolved:
            return target

    handler = RotatingFileHandler(
        target, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)

    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore2").setLevel(logging.WARNING)
    return target
