from __future__ import annotations

from collections.abc import Callable

import httpx2

from quotabubble.providers.base import KeyStatus, Provider, ProviderStatus
from quotabubble.providers.kimi import KimiProvider


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


def test_missing_key_reports_no_credentials() -> None:
    assert KimiProvider().fetch().status is ProviderStatus.NO_CREDENTIALS


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
