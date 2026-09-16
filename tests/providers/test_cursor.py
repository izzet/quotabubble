from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.cursor import CursorProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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
    assert [window.short for window in snapshot.windows] == ["auto", "api"]
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
