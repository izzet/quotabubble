from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx2

from quotabubble.providers.base import (
    ApiKeyProvider,
    KeyStatus,
    Provider,
    ProviderStatus,
)
from quotabubble.providers.opencode import OpenCodeProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_implements_provider_and_api_key_protocols() -> None:
    provider = OpenCodeProvider()
    assert isinstance(provider, Provider)
    assert isinstance(provider, ApiKeyProvider)


def test_detect_reflects_key_presence() -> None:
    assert OpenCodeProvider(api_key="secret").detect() is True
    assert OpenCodeProvider(key_resolver=lambda: "resolved").detect() is True
    assert OpenCodeProvider(key_resolver=lambda: None).detect() is False


def test_missing_key_reports_no_credentials() -> None:
    provider = OpenCodeProvider(key_resolver=lambda: None)
    snapshot = provider.fetch()
    assert snapshot.status is ProviderStatus.NO_CREDENTIALS
    assert snapshot.message == "Add an OpenCode API key"


def test_parses_rolling_weekly_monthly_windows() -> None:
    body = (FIXTURES / "opencode_usage.json").read_text(encoding="utf-8")
    now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=UTC)

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/zen/go/v1/usage"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx2.Response(200, text=body)

    provider = OpenCodeProvider(
        api_key="test-key",
        clock=lambda: now,
        client=_client(handler),
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    # In fixture: weekly is 45%, monthly is 30% -> weekly is more constrained
    assert [w.label for w in snapshot.windows] == ["5h", "Weekly", "Monthly"]
    assert [w.short for w in snapshot.windows] == ["5h", "wk", "mo"]
    assert [w.used_pct for w in snapshot.windows] == [15.5, 45.0, 30.0]
    assert snapshot.windows[0].resets_at == datetime(2026, 9, 16, 14, 0, 0, tzinfo=UTC)
    assert snapshot.windows[1].resets_at == datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)


def test_prefers_monthly_when_more_constrained_than_weekly() -> None:
    payload = json.dumps(
        {
            "usage": {
                "rolling": {"percent": 10.0, "resetInSec": 3600},
                "weekly": {"percent": 25.0, "resetInSec": 86400},
                "monthly": {"percent": 80.0, "resetInSec": 600000},
            }
        }
    )
    provider = OpenCodeProvider(
        api_key="test-key",
        client=_client(lambda req: httpx2.Response(200, text=payload)),
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    # Monthly (80%) is more constrained than Weekly (25%) -> Monthly is second window
    assert [w.label for w in snapshot.windows] == ["5h", "Monthly", "Weekly"]
    assert [w.short for w in snapshot.windows] == ["5h", "mo", "wk"]
    assert [w.used_pct for w in snapshot.windows] == [10.0, 80.0, 25.0]


def test_handles_partial_windows() -> None:
    payload = json.dumps(
        {
            "usage": {
                "rolling": {"percent": 5.0, "resetInSec": 1800},
                "monthly": {"percent": 20.0, "resetInSec": 50000},
            }
        }
    )
    provider = OpenCodeProvider(
        api_key="test-key",
        client=_client(lambda req: httpx2.Response(200, text=payload)),
    )
    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [w.label for w in snapshot.windows] == ["5h", "Monthly"]
    assert [w.short for w in snapshot.windows] == ["5h", "mo"]


def test_auth_error_reports_expired() -> None:
    provider = OpenCodeProvider(
        api_key="bad-key",
        client=_client(lambda req: httpx2.Response(401)),
    )
    snapshot = provider.fetch()
    assert snapshot.status is ProviderStatus.EXPIRED


def test_network_error_reports_error() -> None:
    def handler(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    provider = OpenCodeProvider(api_key="key", client=_client(handler))
    snapshot = provider.fetch()
    assert snapshot.status is ProviderStatus.ERROR
    assert "connection refused" in (snapshot.message or "")


def test_malformed_json_reports_error() -> None:
    provider = OpenCodeProvider(
        api_key="key",
        client=_client(lambda req: httpx2.Response(200, text="not-json")),
    )
    snapshot = provider.fetch()
    assert snapshot.status is ProviderStatus.ERROR


def test_missing_usage_container_reports_error() -> None:
    provider = OpenCodeProvider(
        api_key="key",
        client=_client(lambda req: httpx2.Response(200, text="{}")),
    )
    snapshot = provider.fetch()
    assert snapshot.status is ProviderStatus.ERROR
    assert snapshot.message == "Missing usage fields"


def test_check_api_key_validations() -> None:
    provider = OpenCodeProvider(
        client=_client(
            lambda req: httpx2.Response(
                200
                if req.headers.get("Authorization") == "Bearer valid-key"
                else 401
            )
        )
    )
    assert provider.check_api_key("") is KeyStatus.MISSING
    assert provider.check_api_key("   ") is KeyStatus.MISSING
    assert provider.check_api_key("valid-key") is KeyStatus.VALID
    assert provider.check_api_key("invalid-key") is KeyStatus.INVALID

    unreachable_provider = OpenCodeProvider(
        client=_client(lambda req: (_ for _ in ()).throw(httpx2.ConnectError("down")))
    )
    assert unreachable_provider.check_api_key("any-key") is KeyStatus.UNREACHABLE
