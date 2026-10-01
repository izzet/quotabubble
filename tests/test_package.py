from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

import pytest

import quotabubble
from quotabubble import _resolve_version


def test_version_matches_pyproject() -> None:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    assert quotabubble.__version__ == data["project"]["version"]


def test_resolve_version_from_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata, "version", lambda _name: "1.2.3")
    assert _resolve_version() == "1.2.3"


def test_resolve_version_fallback_to_pyproject(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_version(_name: str) -> str:
        raise metadata.PackageNotFoundError

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(metadata, "version", fake_version)
    assert _resolve_version() == data["project"]["version"]


def test_resolve_version_raises_when_unresolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_version(_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(metadata, "version", fake_version)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)
    with pytest.raises(RuntimeError, match="Cannot determine QuotaBubble version"):
        _resolve_version()
