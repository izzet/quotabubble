from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.base import Provider, ProviderStatus
from quotabubble.providers.grok import GrokProvider, default_credentials_path, read_credentials

FUTURE = "2099-01-01T00:00:00Z"


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _auth(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _routes(billing: dict | int, settings: dict | int | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        target = billing if request.url.path.endswith("/billing") else settings
        if isinstance(target, int):
            return httpx2.Response(target)
        if target is None:
            return httpx2.Response(404)
        return httpx2.Response(200, json=target)

    return _client(handler)


def test_implements_provider_protocol() -> None:
    assert isinstance(GrokProvider(), Provider)


def test_default_path_honours_grok_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROK_HOME", str(tmp_path))

    assert default_credentials_path() == tmp_path / "auth.json"


def test_read_credentials_prefers_cli_scope(tmp_path: Path) -> None:
    path = _auth(
        tmp_path,
        {
            "https://accounts.x.ai/sign-in": {"key": "fallback"},
            "https://auth.x.ai::client-1": {"key": "preferred", "expires_at": FUTURE},
        },
    )

    token, expires_at = read_credentials(path)

    assert token == "preferred"
    assert expires_at is not None


def test_read_credentials_rejects_missing_or_malformed_files(tmp_path: Path) -> None:
    assert read_credentials(tmp_path / "missing.json") is None
    assert read_credentials(_auth(tmp_path, ["not", "a", "dict"])) is None
    assert read_credentials(_auth(tmp_path, {"https://auth.x.ai::c": {"key": ""}})) is None
    assert read_credentials(_auth(tmp_path, {"https://other": {"key": "k"}})) is None


def test_detect_reflects_login_state(tmp_path: Path) -> None:
    assert GrokProvider(credentials_path=tmp_path / "none.json").detect() is False
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})
    assert GrokProvider(credentials_path=auth).detect() is True


def test_missing_login_reports_no_credentials(tmp_path: Path) -> None:
    snapshot = GrokProvider(credentials_path=tmp_path / "none.json").fetch()

    assert snapshot.status is ProviderStatus.NO_CREDENTIALS


def test_expired_token_reports_expired_without_calling_api(tmp_path: Path) -> None:
    auth = _auth(
        tmp_path, {"https://auth.x.ai::c": {"key": "k", "expires_at": "2020-01-01T00:00:00Z"}}
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("must not call the API with an expired token")

    snapshot = GrokProvider(credentials_path=auth, client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED


def test_credit_usage_becomes_a_window_with_plan(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "tok", "expires_at": 4_000_000_000}})
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path.endswith("/billing"):
            return httpx2.Response(
                200,
                json={
                    "config": {
                        "creditUsagePercent": 42.5,
                        "currentPeriod": {"end": "2026-10-01T00:00:00Z"},
                    }
                },
            )
        return httpx2.Response(200, json={"subscription_tier_display": "SuperGrok"})

    snapshot = GrokProvider(credentials_path=auth, client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.plan == "SuperGrok"
    (window,) = snapshot.windows
    assert (window.label, window.short, window.used_pct) == ("Credits", "cr", 42.5)
    assert window.resets_at is not None
    assert all(r.headers["Authorization"] == "Bearer tok" for r in seen)
    assert all(r.headers["x-xai-token-auth"] == "xai-grok-cli" for r in seen)


def test_usage_falls_back_to_on_demand_ratio_and_tier(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})
    billing = {
        "config": {
            "onDemandUsed": {"val": "25"},
            "onDemandCap": {"val": 100},
            "billingPeriodEnd": "2026-10-01T00:00:00Z",
            "subscriptionTier": "Heavy",
        }
    }

    snapshot = GrokProvider(credentials_path=auth, client=_routes(billing)).fetch()

    assert snapshot.windows[0].used_pct == 25.0
    assert snapshot.windows[0].resets_at is not None
    assert snapshot.plan == "Heavy"


def test_period_without_percent_shows_plan_but_no_bar(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})
    billing = {"config": {"currentPeriod": {"end": "2026-10-01T00:00:00Z"}}}

    snapshot = GrokProvider(credentials_path=auth, client=_routes(billing, 500)).fetch()

    assert snapshot.status is ProviderStatus.OK
    assert snapshot.windows == []


def test_rejected_token_reports_expired(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})

    snapshot = GrokProvider(credentials_path=auth, client=_routes(401)).fetch()

    assert snapshot.status is ProviderStatus.EXPIRED


def test_unexpected_responses_report_error(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})

    assert GrokProvider(credentials_path=auth, client=_routes(500)).fetch().status is (
        ProviderStatus.ERROR
    )
    assert GrokProvider(credentials_path=auth, client=_routes({"x": 1})).fetch().status is (
        ProviderStatus.ERROR
    )
    not_json = _client(lambda request: httpx2.Response(200, text="nope"))
    assert GrokProvider(credentials_path=auth, client=not_json).fetch().status is (
        ProviderStatus.ERROR
    )


def test_network_error_reports_error(tmp_path: Path) -> None:
    auth = _auth(tmp_path, {"https://auth.x.ai::c": {"key": "k"}})

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    snapshot = GrokProvider(credentials_path=auth, client=_client(handler)).fetch()

    assert snapshot.status is ProviderStatus.ERROR
