from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx2

from quotabubble.providers.base import KeyStatus, Provider, ProviderStatus
from quotabubble.providers.zai import ZaiProvider


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _respond(payload: object, status: int = 200) -> httpx2.Client:
    return _client(lambda request: httpx2.Response(status, json=payload))


def _millis(delta: timedelta) -> int:
    return int((datetime.now(tz=UTC) + delta).timestamp() * 1000)


def _payload(*limits: dict, plan: str | None = "Pro") -> dict:
    data: dict = {"limits": list(limits)}
    if plan:
        data["planName"] = plan
    return {"success": True, "code": 200, "data": data}


def test_implements_provider_protocol() -> None:
    assert isinstance(ZaiProvider(), Provider)


def test_detect_reflects_key_presence() -> None:
    assert ZaiProvider(api_key="k").detect() is True
    assert ZaiProvider().detect() is False


def test_missing_key_reports_no_credentials() -> None:
    assert ZaiProvider().fetch().status is ProviderStatus.NO_CREDENTIALS


def test_windows_are_ordered_and_named_by_duration() -> None:
    payload = _payload(
        {
            "type": "TOKENS_LIMIT",
            "unit": 6,
            "number": 1,
            "percentage": 40,
            "nextResetTime": _millis(timedelta(days=3)),
        },
        {
            "type": "TOKENS_LIMIT",
            "unit": 3,
            "number": 5,
            "percentage": 12,
            "nextResetTime": _millis(timedelta(hours=2)),
        },
        {"type": "TIME_LIMIT", "unit": 5, "number": 1, "percentage": 7},
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx2.Response(200, json=payload)

    snapshot = ZaiProvider(api_key="test-key", client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.plan == "Pro"
    session, weekly, mcp = snapshot.windows
    assert (session.label, session.used_pct) == ("5h", 12.0)
    assert session.resets_at is not None
    assert (weekly.label, weekly.used_pct) == ("Weekly", 40.0)
    assert (mcp.label, mcp.key) == ("MCP", "mcp")


def test_single_token_window_is_the_session_window() -> None:
    payload = _payload({"type": "TOKENS_LIMIT", "unit": 1, "number": 1, "percentage": 5})

    snapshot = ZaiProvider(api_key="k", client=_respond(payload)).fetch()

    assert [window.label for window in snapshot.windows] == ["5h"]


def test_unrecognised_token_window_is_labelled_generically() -> None:
    payload = _payload(
        {"type": "TOKENS_LIMIT", "unit": 3, "number": 1, "percentage": 1},
        {"type": "TOKENS_LIMIT", "unit": 3, "number": 5, "percentage": 2},
        {"type": "TOKENS_LIMIT", "unit": 6, "number": 1, "percentage": 3},
    )

    snapshot = ZaiProvider(api_key="k", client=_respond(payload)).fetch()

    assert [window.label for window in snapshot.windows] == ["Tokens", "5h", "Weekly"]


def test_percentage_is_recomputed_from_counts_when_available() -> None:
    payload = _payload(
        {"type": "TOKENS_LIMIT", "unit": 3, "number": 5, "percentage": 1, "usage": 200,
         "currentValue": 50},
        {"type": "TIME_LIMIT", "unit": 5, "number": 1, "percentage": 1, "usage": 100,
         "remaining": 80},
    )

    snapshot = ZaiProvider(api_key="k", client=_respond(payload)).fetch()

    assert [window.used_pct for window in snapshot.windows] == [25.0, 20.0]


def test_implausibly_distant_reset_is_dropped() -> None:
    payload = _payload(
        {
            "type": "TOKENS_LIMIT",
            "unit": 3,
            "number": 5,
            "percentage": 10,
            "nextResetTime": _millis(timedelta(days=2)),
        }
    )

    snapshot = ZaiProvider(api_key="k", client=_respond(payload)).fetch()

    assert snapshot.windows[0].resets_at is None


def test_missing_plan_and_limits_are_tolerated() -> None:
    assert ZaiProvider(api_key="k", client=_respond(_payload(plan=None))).fetch().plan is None
    no_limits = {"data": {"limits": "junk"}}
    assert ZaiProvider(api_key="k", client=_respond(no_limits)).fetch().windows == []


def test_invalid_key_reports_error() -> None:
    snapshot = ZaiProvider(api_key="bad", client=_respond({}, 401)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "Invalid Z.ai API key"


def test_body_level_auth_failure_reports_invalid_key() -> None:
    body = {"code": 401, "msg": "token expired or incorrect", "success": False}

    snapshot = ZaiProvider(api_key="bad", client=_respond(body)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "Invalid Z.ai API key"


def test_account_without_a_coding_plan_is_reported_clearly() -> None:
    body = {"code": 500, "msg": "当前用户不存在coding plan", "success": False}

    snapshot = ZaiProvider(api_key="k", client=_respond(body)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "No Coding Plan on this Z.ai account"


def test_other_body_level_failures_surface_their_message() -> None:
    with_msg = {"code": 9, "msg": "try later", "success": False}
    without_msg = {"code": 9, "success": False}

    assert ZaiProvider(api_key="k", client=_respond(with_msg)).fetch().message == "try later"
    assert ZaiProvider(api_key="k", client=_respond(without_msg)).fetch().message == (
        "Z.ai rejected the request"
    )


def test_unexpected_status_and_body_report_error() -> None:
    assert ZaiProvider(api_key="k", client=_respond({}, 500)).fetch().status is (
        ProviderStatus.ERROR
    )
    assert ZaiProvider(api_key="k", client=_respond({"data": 1})).fetch().status is (
        ProviderStatus.ERROR
    )
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert ZaiProvider(api_key="k", client=not_json).fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert ZaiProvider(api_key="k", client=_client(handler)).fetch().status is (
        ProviderStatus.ERROR
    )


def test_check_api_key_statuses() -> None:
    assert ZaiProvider().check_api_key("") is KeyStatus.MISSING
    assert ZaiProvider(client=_respond(_payload())).check_api_key("k") is KeyStatus.VALID
    assert ZaiProvider(client=_respond({}, 401)).check_api_key("k") is KeyStatus.INVALID
    assert ZaiProvider(client=_respond({}, 500)).check_api_key("k") is KeyStatus.UNREACHABLE
    auth_failure = {"code": 1001, "msg": "no header", "success": False}
    assert ZaiProvider(client=_respond(auth_failure)).check_api_key("k") is KeyStatus.INVALID
    no_plan = {"code": 500, "msg": "no coding plan", "success": False}
    assert ZaiProvider(client=_respond(no_plan)).check_api_key("k") is KeyStatus.VALID
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert ZaiProvider(client=not_json).check_api_key("k") is KeyStatus.UNREACHABLE

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert ZaiProvider(client=_client(handler)).check_api_key("k") is KeyStatus.UNREACHABLE
