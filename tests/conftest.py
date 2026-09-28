from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_default_settings_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from quotabubble.app import settings

    monkeypatch.setattr(
        settings, "default_settings_path", lambda: tmp_path / "settings.json"
    )


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
