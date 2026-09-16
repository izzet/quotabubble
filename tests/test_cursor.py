from __future__ import annotations

import base64
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.credentials_cursor import (
    read_cursor_access_token,
    resolve_cursor_session_token,
    session_cookie_from_access_token,
)
from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.cursor import CursorProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _fake_jwt(user_id: str) -> str:
    header = _b64url(b'{"alg":"none"}')
    payload = _b64url(json.dumps({"sub": f"auth0|{user_id}"}).encode("utf-8"))
    return f"{header}.{payload}.sig"


def _seed_db(path: Path, token: str, *, quoted: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        value = json.dumps(token) if quoted else token
        connection.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            ("cursorAuth/accessToken", value),
        )
        connection.commit()
    finally:
        connection.close()


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(CursorProvider(token_provider=lambda: None), Provider)


def test_detect_reflects_token_presence() -> None:
    assert CursorProvider(token_provider=lambda: "user%3A%3Atoken").detect() is True
    assert CursorProvider(token_provider=lambda: None).detect() is False


def test_missing_token_reports_no_credentials() -> None:
    provider = CursorProvider(token_provider=lambda: None)
    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_parses_auto_and_api_windows() -> None:
    body = (FIXTURES / "cursor_usage.json").read_text(encoding="utf-8")
    token = "user_123%3A%3Afake"

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/usage-summary"
        assert request.headers["Cookie"] == f"WorkosCursorSessionToken={token}"
        assert request.headers["Origin"] == "https://cursor.com"
        return httpx2.Response(200, text=body)

    provider = CursorProvider(token_provider=lambda: token, client=_client(handler))
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["Auto", "API"]
    assert [window.short for window in snapshot.windows] == ["aut", "api"]
    assert [round(window.used_pct, 1) for window in snapshot.windows] == [42.5, 18.0]
    assert snapshot.plan == "Pro"
    assert snapshot.windows[0].resets_at == snapshot.windows[1].resets_at
    assert snapshot.windows[0].resets_at is not None


def test_auth_error_reports_expired() -> None:
    provider = CursorProvider(
        token_provider=lambda: "user%3A%3Ax",
        client=_client(lambda request: httpx2.Response(401)),
    )
    assert provider.fetch().status is ProviderStatus.EXPIRED


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = CursorProvider(token_provider=lambda: "user%3A%3Ax", client=_client(handler))
    assert provider.fetch().status is ProviderStatus.ERROR


def test_session_cookie_from_jwt() -> None:
    token = _fake_jwt("user_abc")
    assert session_cookie_from_access_token(token) == f"user_abc%3A%3A{token}"


def test_session_cookie_accepts_prebuilt_value() -> None:
    assert session_cookie_from_access_token("user::jwt") == "user%3A%3Ajwt"
    assert session_cookie_from_access_token("user%3A%3Ajwt") == "user%3A%3Ajwt"


def test_read_access_token_from_sqlite(tmp_path: Path) -> None:
    token = _fake_jwt("user_db")
    db_path = tmp_path / "state.vscdb"
    _seed_db(db_path, token)
    assert read_cursor_access_token(db_path) == token


def test_read_access_token_strips_json_quotes(tmp_path: Path) -> None:
    token = _fake_jwt("user_quoted")
    db_path = tmp_path / "state.vscdb"
    _seed_db(db_path, token, quoted=True)
    assert read_cursor_access_token(db_path) == token


def test_resolve_prefers_env_over_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "state.vscdb"
    _seed_db(db_path, _fake_jwt("user_db"))
    env_token = _fake_jwt("user_env")
    monkeypatch.setenv("CURSOR_SESSION_TOKEN", env_token)
    assert resolve_cursor_session_token(db_path) == f"user_env%3A%3A{env_token}"


def test_resolve_reads_db_when_env_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURSOR_SESSION_TOKEN", raising=False)
    token = _fake_jwt("user_db")
    db_path = tmp_path / "state.vscdb"
    _seed_db(db_path, token)
    assert resolve_cursor_session_token(db_path) == f"user_db%3A%3A{token}"


def test_resolve_falls_back_to_auth_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURSOR_SESSION_TOKEN", raising=False)
    token = _fake_jwt("user_auth")
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"accessToken": token}), encoding="utf-8")
    monkeypatch.setattr(
        "quotabubble.credentials_cursor.default_cursor_db_path",
        lambda: tmp_path / "missing.vscdb",
    )
    monkeypatch.setattr(
        "quotabubble.credentials_cursor.default_cursor_auth_paths",
        lambda: [auth_path],
    )
    assert resolve_cursor_session_token() == f"user_auth%3A%3A{token}"


def test_read_access_token_copy_fallback(tmp_path: Path, monkeypatch) -> None:
    import quotabubble.credentials_cursor as cursor_creds

    token = _fake_jwt("user_locked")
    db_path = tmp_path / "state.vscdb"
    _seed_db(db_path, token)

    calls = {"n": 0}
    real_query = cursor_creds._query_access_token

    def flaky_query(path: Path) -> str | None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_query(path)

    monkeypatch.setattr(cursor_creds, "_query_access_token", flaky_query)
    assert read_cursor_access_token(db_path) == token
    assert calls["n"] == 2
