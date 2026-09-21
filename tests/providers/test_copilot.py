from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.copilot import CopilotProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _credentials(token: str) -> Callable[[str], list[tuple[str, bytes]]]:
    return lambda hint: [("https://github.com:tester.copilot-cli", token.encode("utf-16-le"))]


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(CopilotProvider(credential_provider=lambda hint: []), Provider)


def test_detect_reflects_token_presence() -> None:
    assert CopilotProvider(credential_provider=_credentials("gho_x")).detect() is True
    assert CopilotProvider(credential_provider=lambda hint: []).detect() is False


def test_missing_token_reports_no_credentials() -> None:
    provider = CopilotProvider(credential_provider=lambda hint: [])

    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_parses_premium_and_chat_windows() -> None:
    body = (FIXTURES / "copilot_usage.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "token gho_x"
        assert request.headers["Editor-Version"] == "vscode/1.96.2"
        return httpx2.Response(200, text=body)

    provider = CopilotProvider(
        credential_provider=_credentials("gho_x"), client=_client(handler)
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["Premium", "Chat"]
    assert [round(window.used_pct, 1) for window in snapshot.windows] == [40.0, 25.0]
    assert snapshot.plan == "Individual"
    assert snapshot.windows[0].resets_at is not None


def test_auth_error_reports_expired() -> None:
    provider = CopilotProvider(
        credential_provider=_credentials("gho_x"),
        client=_client(lambda request: httpx2.Response(401)),
    )

    assert provider.fetch().status is ProviderStatus.EXPIRED


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = CopilotProvider(
        credential_provider=_credentials("gho_x"), client=_client(handler)
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_linux_utf8_token_is_not_misread_as_utf16() -> None:
    provider = CopilotProvider(credential_provider=lambda hint: [("copilot", b"gho_token")])

    assert provider._token() == "gho_token"
