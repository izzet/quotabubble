from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import KeyStatus, Provider, ProviderStatus
from quotabubble.providers.deepseek import DeepSeekProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(DeepSeekProvider(), Provider)


def test_detect_reflects_key_presence() -> None:
    assert DeepSeekProvider(api_key="secret").detect() is True
    assert DeepSeekProvider().detect() is False


def test_missing_key_reports_no_credentials() -> None:
    assert DeepSeekProvider().fetch().status is ProviderStatus.NO_CREDENTIALS


def test_balance_becomes_credits() -> None:
    body = (FIXTURES / "deepseek_balance.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx2.Response(200, text=body)

    snapshot = DeepSeekProvider(api_key="test-key", client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []
    assert snapshot.credits is not None
    assert snapshot.credits.display == "$12.34"


def test_invalid_key_reports_error() -> None:
    provider = DeepSeekProvider(
        api_key="bad", client=_client(lambda request: httpx2.Response(401))
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = DeepSeekProvider(api_key="secret", client=_client(handler))

    assert provider.fetch().status is ProviderStatus.ERROR


def test_check_api_key_valid() -> None:
    provider = DeepSeekProvider(
        client=_client(lambda request: httpx2.Response(200, text="{}"))
    )

    assert provider.check_api_key("secret") is KeyStatus.VALID


def test_check_api_key_invalid() -> None:
    provider = DeepSeekProvider(client=_client(lambda request: httpx2.Response(401)))

    assert provider.check_api_key("secret") is KeyStatus.INVALID


def test_check_api_key_unreachable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = DeepSeekProvider(client=_client(handler))

    assert provider.check_api_key("secret") is KeyStatus.UNREACHABLE


def test_check_api_key_missing() -> None:
    assert DeepSeekProvider().check_api_key("") is KeyStatus.MISSING
