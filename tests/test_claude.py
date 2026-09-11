from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.claude import ClaudeProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _write_credentials(tmp_path: Path) -> Path:
    target = tmp_path / "credentials.json"
    source = FIXTURES / "claude_credentials.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(ClaudeProvider(), Provider)


def test_missing_credentials_reports_no_credentials(tmp_path: Path) -> None:
    provider = ClaudeProvider(credentials_path=tmp_path / "absent.json")

    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_fetch_parses_quota_windows(tmp_path: Path) -> None:
    body = (FIXTURES / "claude_usage.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["anthropic-beta"] == "oauth-2025-04-20"
        return httpx2.Response(200, text=body)

    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path), client=_client(handler)
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["5h", "7d"]
    assert snapshot.windows[0].used_pct == 42.0
    assert snapshot.windows[1].used_pct == 71.0
    assert snapshot.windows[0].resets_at is not None


def test_rejected_credentials_report_expired(tmp_path: Path) -> None:
    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(401)),
    )

    assert provider.fetch().status is ProviderStatus.EXPIRED


def test_server_error_reports_error(tmp_path: Path) -> None:
    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(503)),
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_malformed_body_reports_error(tmp_path: Path) -> None:
    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(200, text="not json")),
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path), client=_client(handler)
    )

    assert provider.fetch().status is ProviderStatus.ERROR
