from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

TOKEN_KEY = "cursorAuth/accessToken"
SESSION_TOKEN_ENV = "CURSOR_SESSION_TOKEN"
_ITEM_TABLE = "ItemTable"


def default_cursor_db_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "state.vscdb"
        )
    return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def _sanitize_token(raw: str) -> str | None:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if not text:
        return None
    return text


def _query_access_token(path: Path) -> str | None:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=1.0)
    try:
        row = connection.execute(
            f"SELECT value FROM {_ITEM_TABLE} WHERE key = ?",
            (TOKEN_KEY,),
        ).fetchone()
    except sqlite3.Error:
        raise
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str):
        return None
    return _sanitize_token(row[0])


def _copy_db_tree(source: Path, destination: Path) -> None:
    shutil.copy2(source, destination)
    for suffix in ("-wal", "-shm"):
        side = Path(str(source) + suffix)
        if side.is_file():
            shutil.copy2(side, Path(str(destination) + suffix))


def read_cursor_access_token(db_path: Path | None = None) -> str | None:
    path = db_path or default_cursor_db_path()
    if not path.is_file():
        return None
    try:
        return _query_access_token(path)
    except sqlite3.OperationalError:
        pass
    except sqlite3.Error:
        return None

    try:
        with tempfile.TemporaryDirectory(prefix="quotabubble-cursor-") as tmp:
            copied = Path(tmp) / "state.vscdb"
            _copy_db_tree(path, copied)
            return _query_access_token(copied)
    except (OSError, sqlite3.Error):
        return None


def _b64url_json(segment: str) -> dict | None:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def user_id_from_access_token(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = _b64url_json(parts[1])
    if payload is None:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    if "|" in sub:
        return sub.rsplit("|", 1)[-1] or None
    return sub


def session_cookie_from_access_token(token: str) -> str | None:
    cleaned = _sanitize_token(token)
    if cleaned is None:
        return None
    if "%3A%3A" in cleaned.upper() or "::" in cleaned:
        if "::" in cleaned and "%3A%3A" not in cleaned.upper():
            user_id, _, rest = cleaned.partition("::")
            if user_id and rest:
                return f"{user_id}%3A%3A{rest}"
        return cleaned
    user_id = user_id_from_access_token(cleaned)
    if user_id is None:
        return None
    return f"{user_id}%3A%3A{cleaned}"


def resolve_cursor_session_token(db_path: Path | None = None) -> str | None:
    env = os.environ.get(SESSION_TOKEN_ENV)
    if env:
        cookie = session_cookie_from_access_token(env)
        if cookie:
            return cookie
    access_token = read_cursor_access_token(db_path)
    if access_token is None:
        return None
    return session_cookie_from_access_token(access_token)
