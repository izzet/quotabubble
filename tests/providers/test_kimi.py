from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from quotabubble.credentials.kimi import KimiCodeLogin
from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.kimi import KimiProvider, _usage_url

NOW = 1_000.0

USAGE = {
    "user": {"membership": {"level": "BASIC"}},
    "usage": {"limit": "100", "used": "25", "resetTime": "2026-09-29T00:00:00Z"},
    "limits": [
        {
            "window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
            "detail": {"limit": 50, "remaining": 40, "resetAt": "2026-09-22T15:00:00Z"},
        }
    ],
}


@pytest.fixture(autouse=True)
def _isolated_kimi_home(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "no-kimi-code"))
    monkeypatch.setenv("KIMI_CODE_BASE_URL", "https://api.kimi.test")


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _respond(payload: object, status: int = 200) -> httpx2.Client:
    return _client(lambda request: httpx2.Response(status, json=payload))


def _login(expires_at: float | None = NOW + 900) -> KimiCodeLogin:
    return KimiCodeLogin("cli-token", "refresh", expires_at)


def _provider(client: httpx2.Client, login: KimiCodeLogin | None = None) -> KimiProvider:
    resolved = login if login is not None else _login()
    return KimiProvider(client=client, login_reader=lambda: resolved, clock=lambda: NOW)


def test_implements_provider_protocol() -> None:
    provider = KimiProvider()

    assert isinstance(provider, Provider)
    assert provider.uses_api_key is False


def test_detect_reflects_a_cli_login() -> None:
    assert KimiProvider(login_reader=lambda: _login()).detect() is True
    assert KimiProvider(login_reader=lambda: None).detect() is False


def test_missing_login_reports_no_credentials() -> None:
    snapshot = KimiProvider(login_reader=lambda: None).fetch()

    assert snapshot.status is ProviderStatus.NO_CREDENTIALS
    assert snapshot.message == "Sign in with Kimi Code"


def test_cli_login_is_used_with_identity_headers(tmp_path, monkeypatch) -> None:
    home = tmp_path / "kimi-home"
    home.mkdir()
    (home / "device_id").write_text("dev-1", encoding="utf-8")
    monkeypatch.setenv("KIMI_CODE_HOME", str(home))

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url == "https://api.kimi.test/coding/v1/usages"
        assert request.headers["Authorization"] == "Bearer cli-token"
        assert request.headers["X-Msh-Platform"] == "kimi_code_cli"
        assert request.headers["X-Msh-Device-Id"] == "dev-1"
        assert request.headers["User-Agent"].startswith("QuotaBubble/")
        return httpx2.Response(200, json=USAGE)

    snapshot = _provider(_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.plan == "Moderato"
    session, weekly = snapshot.windows
    assert (session.label, session.short, session.used_pct) == ("5h", "5h", 20.0)
    assert session.resets_at is not None
    assert (weekly.label, weekly.short, weekly.used_pct) == ("Weekly", "wk", 25.0)
    assert weekly.resets_at is not None


def test_empty_usage_body_is_ok_with_no_windows() -> None:
    snapshot = _provider(_respond({})).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []
    assert snapshot.plan is None


def test_plan_name_field_is_preferred() -> None:
    payload = {"planName": " Pro ", "user": {"membership": {"level": "BASIC"}}}

    assert _provider(_respond(payload)).fetch().plan == "Pro"


def test_epoch_reset_and_unknown_plan_are_handled() -> None:
    payload = {
        "user": {"membership": {"level": "LEVEL_MEGA"}},
        "usage": {"limit": 10, "used": 5, "reset_time": 1_790_000_000},
    }

    snapshot = _provider(_respond(payload)).fetch()

    assert snapshot.plan == "Mega"
    assert snapshot.windows[0].resets_at is not None


def test_day_window_is_labelled_by_duration() -> None:
    payload = {
        "limits": [
            {
                "window": {"duration": 1, "timeUnit": "TIME_UNIT_DAY"},
                "detail": {"limit": 10, "used": 1},
            }
        ]
    }

    assert _provider(_respond(payload)).fetch().windows[0].label == "1d"


def test_payload_without_usable_limits_yields_no_windows() -> None:
    payload = {"usage": {"limit": 0, "used": 0}, "limits": [{"detail": {}}, "junk"]}

    snapshot = _provider(_respond(payload)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []


@pytest.mark.parametrize("expires_at", [None, NOW - 1, NOW + 30])
def test_stale_login_reports_expired_without_calling_the_api(expires_at: float | None) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("must not call the API with a stale login")

    snapshot = _provider(_client(handler), _login(expires_at)).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED
    assert snapshot.message == "Open Kimi Code to refresh your login"


def test_rejected_login_reports_expired() -> None:
    assert _provider(_respond({}, 401)).fetch().status is ProviderStatus.EXPIRED
    assert _provider(_respond({}, 403)).fetch().status is ProviderStatus.EXPIRED


def test_login_is_never_sent_without_a_known_region(monkeypatch) -> None:
    monkeypatch.delenv("KIMI_CODE_BASE_URL")

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("a login must not be sent to a guessed host")

    snapshot = _provider(_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert "KIMI_CODE_BASE_URL" in (snapshot.message or "")


def test_unexpected_status_and_body_report_error() -> None:
    assert _provider(_respond({}, 500)).fetch().status is ProviderStatus.ERROR
    assert _provider(_respond([1, 2])).fetch().status is ProviderStatus.ERROR
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert _provider(not_json).fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert _provider(_client(handler)).fetch().status is ProviderStatus.ERROR


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://api.kimi.com", "https://api.kimi.com/coding/v1/usages"),
        ("https://api.kimi.com/", "https://api.kimi.com/coding/v1/usages"),
        ("https://x.test/coding", "https://x.test/coding/v1/usages"),
        ("https://x.test/coding/v1", "https://x.test/coding/v1/usages"),
    ],
)
def test_usage_url_normalises_the_base(base: str, expected: str) -> None:
    assert _usage_url(base) == expected
