from __future__ import annotations

from importlib import metadata
from pathlib import Path


def _resolve_version() -> str:
    try:
        return metadata.version("quotabubble")
    except metadata.PackageNotFoundError:
        pass
    try:
        import tomllib

        for parent in Path(__file__).resolve().parents:
            pyproject_path = parent / "pyproject.toml"
            if pyproject_path.is_file():
                data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
                version = data.get("project", {}).get("version")
                if version:
                    return str(version)
    except Exception:
        pass
    return "0.2.5"


__version__ = _resolve_version()
