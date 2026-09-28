from __future__ import annotations

from collections.abc import Callable

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.zed import ZedProvider


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _respond(payload: object, status: int = 200) -> httpx2.Client:
    return _client(lambda request: httpx2.Response(status, json=payload))


def _provider(client: httpx2.Client) -> ZedProvider:
    return ZedProvider(credentials_reader=lambda: ("42", "tok"), client=client)


def _account(plan: str = "zed_pro", limit: object = 2000, used: object = 500) -> dict:
    return {
        "user": {"id": 42},
        "plan": {
            "plan_v3": plan,
            "subscription_period": {
                "started_at": "2026-09-01T00:00:00Z",
                "ended_at": "2026-10-01T00:00:00Z",
            },
            "usage": {"edit_predictions": {"used": used, "limit": limit}},
        },
    }


def test_implements_provider_protocol() -> None:
    assert isinstance(ZedProvider(), Provider)


def test_detect_reflects_credentials() -> None:
    assert ZedProvider(credentials_reader=lambda: ("42", "tok")).detect() is True
    assert ZedProvider(credentials_reader=lambda: None).detect() is False


def test_missing_credentials_report_no_credentials() -> None:
    snapshot = ZedProvider(credentials_reader=lambda: None).fetch()

    assert snapshot.status is ProviderStatus.NO_CREDENTIALS


def test_edit_predictions_become_a_window_with_reset_and_plan() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == "42 tok"
        return httpx2.Response(200, json=_account())

    snapshot = _provider(_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.plan == "Pro"
    (window,) = snapshot.windows
    assert (window.label, window.short, window.used_pct) == ("Edits", "edit", 25.0)
    assert window.resets_at is not None


def test_limited_object_form_is_supported() -> None:
    snapshot = _provider(_respond(_account(limit={"limited": 200}, used=50))).fetch()

    assert snapshot.windows[0].used_pct == 25.0


def test_usage_is_clamped_to_one_hundred_percent() -> None:
    assert _provider(_respond(_account(used=99999))).fetch().windows[0].used_pct == 100.0


def test_unlimited_or_unusable_limits_show_the_plan_without_a_bar() -> None:
    for limit, used in (("unlimited", 10), (0, 0), (2000, None), ({"limited": None}, 5)):
        snapshot = _provider(_respond(_account(limit=limit, used=used))).fetch()

        assert snapshot.status is ProviderStatus.OK
        assert snapshot.windows == []
        assert snapshot.plan == "Pro"


def test_plan_names_are_friendly() -> None:
    names = {
        "zed_free": "Free",
        "zed_pro_trial": "Pro Trial",
        "zed_student": "Student",
        "zed_business": "Business",
        "zed_enterprise": "Enterprise",
    }
    for raw, expected in names.items():
        assert _provider(_respond(_account(plan=raw))).fetch().plan == expected


def test_payload_without_usage_or_plan_name_is_tolerated() -> None:
    snapshot = _provider(_respond({"plan": {"usage": "junk"}})).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []
    assert snapshot.plan is None


def test_rejected_credentials_report_expired() -> None:
    snapshot = _provider(_respond({}, 401)).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED


def test_unexpected_status_and_body_report_error() -> None:
    assert _provider(_respond({}, 500)).fetch().status is ProviderStatus.ERROR
    assert _provider(_respond({"no": "plan"})).fetch().status is ProviderStatus.ERROR
    assert _provider(_respond([1])).fetch().status is ProviderStatus.ERROR
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert _provider(not_json).fetch().status is ProviderStatus.ERROR


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    assert _provider(_client(handler)).fetch().status is ProviderStatus.ERROR
