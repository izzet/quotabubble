from __future__ import annotations

import json
import os
import sys
from pathlib import Path

OPENCODE_API_KEY_ENV = "OPENCODE_API_KEY"


def default_opencode_auth_paths() -> list[Path]:
    paths: list[Path] = []
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        paths.append(Path(xdg_data) / "opencode" / "auth.json")

    paths.append(Path.home() / ".local" / "share" / "opencode" / "auth.json")

    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            paths.append(Path(localappdata) / "opencode" / "auth.json")
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "opencode" / "auth.json")

    return paths


def default_opencode_config_paths() -> list[Path]:
    paths: list[Path] = []
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        paths.append(Path(xdg_config) / "opencode" / "opencode.jsonc")
        paths.append(Path(xdg_config) / "opencode" / "opencode.json")

    paths.append(Path.home() / ".config" / "opencode" / "opencode.jsonc")
    paths.append(Path.home() / ".config" / "opencode" / "opencode.json")

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "opencode" / "opencode.jsonc")
            paths.append(Path(appdata) / "opencode" / "opencode.json")

    return paths


def _sanitize_key(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text or None


def _strip_jsonc_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
        else:
            if char == '"':
                in_string = True
                result.append(char)
                i += 1
            elif char == "/" and i + 1 < n and text[i + 1] == "/":
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
            elif char == "/" and i + 1 < n and text[i + 1] == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
            else:
                result.append(char)
                i += 1
    return "".join(result)


def read_opencode_api_key_from_auth_file(path: Path) -> str | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None

    for target in ("opencode-go", "opencode", "zen"):
        entry = raw.get(target)
        if isinstance(entry, str):
            cleaned = _sanitize_key(entry)
            if cleaned:
                return cleaned
        elif isinstance(entry, dict):
            for field in ("key", "apiKey", "api_key", "token", "accessToken"):
                val = entry.get(field)
                if isinstance(val, str):
                    cleaned = _sanitize_key(val)
                    if cleaned:
                        return cleaned
    return None


def read_opencode_api_key_from_config_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(_strip_jsonc_comments(text))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None

    for field in ("apiKey", "api_key", "key"):
        val = raw.get(field)
        if isinstance(val, str):
            cleaned = _sanitize_key(val)
            if cleaned:
                return cleaned

    providers = raw.get("provider")
    if isinstance(providers, dict):
        for name in ("opencode", "opencode-go", "zen"):
            prov = providers.get(name)
            if isinstance(prov, dict):
                options = prov.get("options")
                if isinstance(options, dict):
                    val = options.get("apiKey") or options.get("api_key") or options.get("key")
                    if isinstance(val, str):
                        cleaned = _sanitize_key(val)
                        if cleaned:
                            return cleaned
                val = prov.get("apiKey") or prov.get("api_key") or prov.get("key")
                if isinstance(val, str):
                    cleaned = _sanitize_key(val)
                    if cleaned:
                        return cleaned
    return None


def resolve_opencode_api_key(
    api_key: str | None = None,
    auth_paths: list[Path] | None = None,
    config_paths: list[Path] | None = None,
) -> str | None:
    cleaned = _sanitize_key(api_key)
    if cleaned:
        return cleaned

    env_key = _sanitize_key(os.environ.get(OPENCODE_API_KEY_ENV))
    if env_key:
        return env_key

    candidates = auth_paths if auth_paths is not None else default_opencode_auth_paths()
    for p in candidates:
        if p.is_file():
            key = read_opencode_api_key_from_auth_file(p)
            if key:
                return key

    configs = config_paths if config_paths is not None else default_opencode_config_paths()
    for p in configs:
        if p.is_file():
            key = read_opencode_api_key_from_config_file(p)
            if key:
                return key

    return None
