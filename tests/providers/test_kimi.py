from __future__ import annotations

from collections.abc import Callable

import httpx2
import pytest

from quotabubble.credentials.kimi import KimiCodeLogin
from quotabubble.providers.base import KeyStatus, Provider, ProviderStatus
from quotabubble.providers.kimi import KimiProvider, _usage_url


@pytest.fixture(autouse=True)
def _isolated_kimi_home(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "no-kimi-code"))
    monkeypatch.setenv("KIMI_CODE_BASE_URL", "https://api.kimi.test")


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _respond(payload: object, status: int = 200) -> httpx2.Client:
    return _client(lambda request: httpx2.Response(status, json=payload))


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


def test_implements_provider_protocol() -> None:
    assert isinstance(KimiProvider(), Provider)


def test_detect_reflects_key_presence() -> None:
    assert KimiProvider(api_key="k").detect() is True
    assert KimiProvider().detect() is False


def test_missing_key_and_login_report_no_credentials() -> None:
    snapshot = KimiProvider().fetch()

    assert snapshot.status is ProviderStatus.NO_CREDENTIALS
    assert snapshot.message == "Sign in with Kimi Code or add an API key"


def test_usage_becomes_session_and_weekly_windows() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx2.Response(200, json=USAGE)

    snapshot = KimiProvider(api_key="test-key", client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.plan == "Moderato"
    session, weekly = snapshot.windows
    assert (session.label, session.short, session.used_pct) == ("5h", "5h", 20.0)
    assert session.resets_at is not None
    assert (weekly.label, weekly.short, weekly.used_pct) == ("Weekly", "wk", 25.0)
    assert weekly.resets_at is not None


def test_epoch_reset_and_unknown_plan_are_handled() -> None:
    payload = {
        "user": {"membership": {"level": "LEVEL_MEGA"}},
        "usage": {"limit": 10, "used": 5, "reset_time": 1_790_000_000},
    }

    snapshot = KimiProvider(api_key="k", client=_respond(payload)).fetch()

    assert snapshot.plan == "Mega"
    assert snapshot.windows[0].resets_at is not None


def test_day_and_hour_windows_are_labelled_by_duration() -> None:
    payload = {
        "limits": [
            {
                "window": {"duration": 1, "timeUnit": "TIME_UNIT_DAY"},
                "detail": {"limit": 10, "used": 1},
            }
        ]
    }

    snapshot = KimiProvider(api_key="k", client=_respond(payload)).fetch()

    assert snapshot.windows[0].label == "1d"


def test_payload_without_usable_limits_yields_no_windows() -> None:
    payload = {"usage": {"limit": 0, "used": 0}, "limits": [{"detail": {}}, "junk"]}

    snapshot = KimiProvider(api_key="k", client=_respond(payload)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []


def test_invalid_key_reports_error() -> None:
    snapshot = KimiProvider(api_key="bad", client=_respond({}, 401)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "Invalid Kimi Code API key"


def test_unexpected_status_and_body_report_error() -> None:
    assert KimiProvider(api_key="k", client=_respond({}, 500)).fetch().status is (
        ProviderStatus.ERROR
    )
    assert KimiProvider(api_key="k", client=_respond([1, 2])).fetch().status is (
        ProviderStatus.ERROR
    )
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert KimiProvider(api_key="k", client=not_json).fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert KimiProvider(api_key="k", client=_client(handler)).fetch().status is (
        ProviderStatus.ERROR
    )


def test_check_api_key_statuses() -> None:
    assert KimiProvider().check_api_key("") is KeyStatus.MISSING
    assert KimiProvider(client=_respond(USAGE)).check_api_key("k") is KeyStatus.VALID
    assert KimiProvider(client=_respond({}, 403)).check_api_key("k") is KeyStatus.INVALID
    assert KimiProvider(client=_respond({}, 500)).check_api_key("k") is KeyStatus.UNREACHABLE

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert KimiProvider(client=_client(handler)).check_api_key("k") is KeyStatus.UNREACHABLE


NOW = 1_000.0


def _login(expires_at: float | None = NOW + 900) -> KimiCodeLogin:
    return KimiCodeLogin("cli-token", "refresh", expires_at)


def _cli_provider(client: httpx2.Client, login: KimiCodeLogin | None) -> KimiProvider:
    return KimiProvider(client=client, login_reader=lambda: login, clock=lambda: NOW)


def test_detect_reflects_a_cli_login() -> None:
    assert KimiProvider(login_reader=lambda: _login()).detect() is True
    assert KimiProvider(login_reader=lambda: None).detect() is False


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

    snapshot = _cli_provider(_client(handler), _login()).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["5h", "Weekly"]


def test_configured_base_url_is_honoured(monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_BASE_URL", "https://api.kimi.ai/coding/v1")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url == "https://api.kimi.ai/coding/v1/usages"
        return httpx2.Response(200, json={})

    assert _cli_provider(_client(handler), _login()).fetch().status is ProviderStatus.OK


def test_empty_usage_body_is_ok_with_no_windows() -> None:
    snapshot = _cli_provider(_respond({}), _login()).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []
    assert snapshot.plan is None


def test_plan_name_field_is_preferred() -> None:
    payload = {"planName": " Pro ", "user": {"membership": {"level": "BASIC"}}}

    assert _cli_provider(_respond(payload), _login()).fetch().plan == "Pro"


@pytest.mark.parametrize("expires_at", [None, NOW - 1, NOW + 30])
def test_stale_cli_login_reports_expired_without_calling_the_api(
    expires_at: float | None,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("must not call the API with a stale login")

    snapshot = _cli_provider(_client(handler), _login(expires_at)).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED
    assert snapshot.message == "Open Kimi Code to refresh your login"


def test_rejected_cli_login_reports_expired() -> None:
    snapshot = _cli_provider(_respond({}, 401), _login()).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED


def test_api_key_takes_priority_over_the_cli_login() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer explicit-key"
        return httpx2.Response(200, json={})

    provider = KimiProvider(
        api_key="explicit-key", client=_client(handler), login_reader=lambda: _login()
    )

    assert provider.fetch().status is ProviderStatus.OK


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


def test_cli_login_is_never_sent_without_a_known_region(monkeypatch) -> None:
    monkeypatch.delenv("KIMI_CODE_BASE_URL")

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("a CLI login must not be sent to a guessed host")

    snapshot = _cli_provider(_client(handler), _login()).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert "KIMI_CODE_BASE_URL" in (snapshot.message or "")


def test_api_key_falls_back_to_the_default_host_without_a_configured_region(
    monkeypatch,
) -> None:
    monkeypatch.delenv("KIMI_CODE_BASE_URL")
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(str(request.url))
        return httpx2.Response(200, json={})

    provider = KimiProvider(api_key="k", client=_client(handler))
    assert provider.fetch().status is ProviderStatus.OK
    assert provider.check_api_key("k") is KeyStatus.VALID
    assert seen == ["https://api.kimi.com/coding/v1/usages"] * 2
