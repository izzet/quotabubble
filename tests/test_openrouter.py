from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import KeyStatus, Provider, ProviderStatus
from quotabubble.providers.openrouter import OpenRouterProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(OpenRouterProvider(), Provider)


def test_detect_reflects_key_presence() -> None:
    assert OpenRouterProvider(api_key="secret").detect() is True
    assert OpenRouterProvider().detect() is False


def test_missing_key_reports_no_credentials() -> None:
    assert OpenRouterProvider().fetch().status is ProviderStatus.NO_CREDENTIALS


def test_balance_becomes_credits() -> None:
    body = (FIXTURES / "openrouter_credits.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx2.Response(200, text=body)

    snapshot = OpenRouterProvider(api_key="test-key", client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []
    assert snapshot.credits is not None
    assert snapshot.credits.display == "$13.59"


def test_check_api_key_valid() -> None:
    provider = OpenRouterProvider(
        client=_client(lambda request: httpx2.Response(200, text="{}"))
    )

    assert provider.check_api_key("secret") is KeyStatus.VALID


def test_check_api_key_invalid() -> None:
    provider = OpenRouterProvider(client=_client(lambda request: httpx2.Response(401)))

    assert provider.check_api_key("secret") is KeyStatus.INVALID


def test_check_api_key_unreachable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = OpenRouterProvider(client=_client(handler))

    assert provider.check_api_key("secret") is KeyStatus.UNREACHABLE


def test_check_api_key_missing() -> None:
    assert OpenRouterProvider().check_api_key("") is KeyStatus.MISSING
