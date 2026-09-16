from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.codex import CodexProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _write_credentials(tmp_path: Path) -> Path:
    target = tmp_path / "auth.json"
    source = FIXTURES / "codex_credentials.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_protocol() -> None:
    assert isinstance(CodexProvider(), Provider)


def test_missing_credentials_reports_no_credentials(tmp_path: Path) -> None:
    provider = CodexProvider(credentials_path=tmp_path / "absent.json")

    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_fetch_parses_quota_windows_and_plan(tmp_path: Path) -> None:
    body = (FIXTURES / "codex_usage.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-codex-token"
        assert request.headers["User-Agent"] == "codex-cli"
        assert request.headers["ChatGPT-Account-Id"] == "acct-123"
        return httpx2.Response(200, text=body)

    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path), client=_client(handler)
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["5h", "Weekly"]
    assert [window.used_pct for window in snapshot.windows] == [67.0, 54.0]
    assert snapshot.windows[0].resets_at is not None
    assert snapshot.plan == "Plus"
    assert snapshot.credits is None


def test_credits_are_reported_when_present(tmp_path: Path) -> None:
    body = (FIXTURES / "codex_usage_credits.json").read_text(encoding="utf-8")

    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(200, text=body)),
    )
    snapshot = provider.fetch()

    assert snapshot.plan == "Pro"
    assert snapshot.credits is not None
    assert snapshot.credits.display == "12.5"


def test_weekly_window_in_primary_slot_is_classified_by_length(tmp_path: Path) -> None:
    body = (FIXTURES / "codex_usage_weekly_primary.json").read_text(encoding="utf-8")

    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(200, text=body)),
    )
    snapshot = provider.fetch()

    assert [window.label for window in snapshot.windows] == ["Weekly"]
    assert snapshot.windows[0].used_pct == 30.0


def test_rejected_credentials_report_expired(tmp_path: Path) -> None:
    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(403)),
    )

    assert provider.fetch().status is ProviderStatus.EXPIRED


def test_server_error_reports_error(tmp_path: Path) -> None:
    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(500)),
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_malformed_body_reports_error(tmp_path: Path) -> None:
    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(200, text="not json")),
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = CodexProvider(
        credentials_path=_write_credentials(tmp_path), client=_client(handler)
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_detect_reflects_credential_presence(tmp_path: Path) -> None:
    present = CodexProvider(credentials_path=_write_credentials(tmp_path))
    absent = CodexProvider(credentials_path=tmp_path / "absent.json")

    assert present.detect() is True
    assert absent.detect() is False
