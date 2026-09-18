from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from quotabubble.app.logging_setup import setup_logging


def _remove_file_handler(target: Path) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(target):
            root.removeHandler(handler)
            handler.close()


def test_setup_logging_writes_records(tmp_path: Path) -> None:
    target = setup_logging(path=tmp_path / "quotabubble.log")
    try:
        logging.getLogger("quotabubble.test").warning("something happened")
        for handler in logging.getLogger().handlers:
            handler.flush()
        assert "something happened" in target.read_text(encoding="utf-8")
    finally:
        _remove_file_handler(target)


def test_setup_logging_redacts_secrets_end_to_end(tmp_path: Path) -> None:
    target = setup_logging(path=tmp_path / "quotabubble.log")
    try:
        logging.getLogger("quotabubble.test").warning(
            "request failed: Authorization: Bearer sk-abcdefghijklmnopqrstuvwx"
        )
        for handler in logging.getLogger().handlers:
            handler.flush()
        contents = target.read_text(encoding="utf-8")
        assert "sk-abcdefghijklmnopqrstuvwx" not in contents
        assert "[REDACTED]" in contents
    finally:
        _remove_file_handler(target)


def test_setup_logging_redacts_secrets_in_exception_tracebacks(tmp_path: Path) -> None:
    target = setup_logging(path=tmp_path / "quotabubble.log")
    try:
        try:
            raise RuntimeError("auth failed for user jane.doe@example.com")
        except RuntimeError:
            logging.getLogger("quotabubble.test").exception("provider fetch failed")
        for handler in logging.getLogger().handlers:
            handler.flush()
        contents = target.read_text(encoding="utf-8")
        assert "jane.doe@example.com" not in contents
    finally:
        _remove_file_handler(target)
