from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

import quotabubble.providers.claude as claude_module
from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.claude import ClaudeProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(autouse=True)
def no_system_keychain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        claude_module, "enumerate_generic_credentials", lambda _, **__: []
    )


def _write_credentials(tmp_path: Path) -> Path:
    target = tmp_path / "credentials.json"
    source = FIXTURES / "claude_credentials.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _provider_with_body(tmp_path: Path, body: str) -> ClaudeProvider:
    return ClaudeProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(lambda request: httpx2.Response(200, text=body)),
    )


def test_implements_provider_protocol() -> None:
    assert isinstance(ClaudeProvider(), Provider)


def test_missing_credentials_reports_no_credentials(tmp_path: Path) -> None:
    provider = ClaudeProvider(credentials_path=tmp_path / "absent.json")

    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_flat_buckets_are_used_when_limits_are_absent(tmp_path: Path) -> None:
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
    assert [window.label for window in snapshot.windows] == ["5h", "Weekly"]
    assert snapshot.windows[0].used_pct == 42.0
    assert snapshot.windows[1].used_pct == 71.0
    assert snapshot.windows[0].resets_at is not None


def test_limits_are_preferred_and_scoped_windows_are_labelled(tmp_path: Path) -> None:
    body = (FIXTURES / "claude_usage_limits.json").read_text(encoding="utf-8")
    snapshot = _provider_with_body(tmp_path, body).fetch()

    assert [window.label for window in snapshot.windows] == ["5h", "Weekly", "Fable"]
    assert [window.used_pct for window in snapshot.windows] == [9.0, 90.0, 53.0]

    weekly = snapshot.windows[1]
    assert weekly.key == "weekly"
    assert weekly.severity == "critical"
    assert weekly.active is True

    fable = snapshot.windows[2]
    assert fable.key == "weekly_scoped.fable"
    assert fable.scope == "Fable"


def test_credits_are_reported_when_enabled(tmp_path: Path) -> None:
    body = (FIXTURES / "claude_usage_credits.json").read_text(encoding="utf-8")
    snapshot = _provider_with_body(tmp_path, body).fetch()

    assert snapshot.credits is not None
    assert snapshot.credits.display == "$13.59 / $50.00"
    assert snapshot.credits.used_pct == 27.0


def test_credits_absent_when_disabled(tmp_path: Path) -> None:
    body = (FIXTURES / "claude_usage_limits.json").read_text(encoding="utf-8")
    snapshot = _provider_with_body(tmp_path, body).fetch()

    assert snapshot.credits is None


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


def test_rate_limit_reports_retry_after(tmp_path: Path) -> None:
    provider = ClaudeProvider(
        credentials_path=_write_credentials(tmp_path),
        client=_client(
            lambda request: httpx2.Response(429, headers={"Retry-After": "600"})
        ),
    )

    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "HTTP 429"
    assert snapshot.retry_after == 600.0


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


def test_detect_reflects_credential_presence(tmp_path: Path) -> None:
    present = ClaudeProvider(credentials_path=_write_credentials(tmp_path))
    absent = ClaudeProvider(credentials_path=tmp_path / "absent.json")

    assert present.detect() is True
    assert absent.detect() is False


def test_plan_is_reported_from_credentials(tmp_path: Path) -> None:
    body = (FIXTURES / "claude_usage.json").read_text(encoding="utf-8")

    snapshot = _provider_with_body(tmp_path, body).fetch()

    assert snapshot.plan == "Max"
