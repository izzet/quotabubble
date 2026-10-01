from __future__ import annotations

from importlib import metadata
from pathlib import Path


def _resolve_version() -> str:
    try:
        return metadata.version("quotabubble")
    except metadata.PackageNotFoundError:
        pass
    import tomllib

    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.is_file():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if version:
                return str(version)
    raise RuntimeError("Cannot determine QuotaBubble version")


__version__ = _resolve_version()
