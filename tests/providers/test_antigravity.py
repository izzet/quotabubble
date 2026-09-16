from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx2

from quotabubble.providers.antigravity import (
    AntigravityProvider,
    _scan_client_ids,
    _scan_client_secrets,
)
from quotabubble.providers.base import Provider, ProviderStatus

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _reader(blob: bytes | None) -> Callable[[str], bytes | None]:
    return lambda target: blob


def _credentials() -> bytes:
    return json.dumps({"token": {"access_token": "test-token"}}).encode("utf-8")


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _summary_handler(
    summary: str, models: str, tier_name: str | None = "Antigravity"
) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path.endswith("loadCodeAssist"):
            body: dict[str, object] = {"cloudaicompanionProject": "proj-1"}
            if tier_name:
                body["currentTier"] = {"name": tier_name}
            return httpx2.Response(200, text=json.dumps(body))
        if path.endswith("retrieveUserQuotaSummary"):
            return httpx2.Response(200, text=summary)
        if path.endswith("fetchAvailableModels"):
            return httpx2.Response(200, text=models)
        return httpx2.Response(404)

    return handler


def test_implements_provider_protocol() -> None:
    assert isinstance(AntigravityProvider(credential_reader=_reader(None)), Provider)


def test_detect_reflects_credential_presence() -> None:
    present = AntigravityProvider(credential_reader=_reader(_credentials()))
    absent = AntigravityProvider(credential_reader=_reader(None))

    assert present.detect() is True
    assert absent.detect() is False


def test_missing_credentials_reports_no_credentials() -> None:
    provider = AntigravityProvider(credential_reader=_reader(None))

    assert provider.fetch().status is ProviderStatus.NO_CREDENTIALS


def test_summary_prefers_the_gemini_group() -> None:
    summary = (FIXTURES / "antigravity_quota_summary.json").read_text(encoding="utf-8")
    models = (FIXTURES / "antigravity_models.json").read_text(encoding="utf-8")
    provider = AntigravityProvider(
        credential_reader=_reader(_credentials()),
        client=_client(_summary_handler(summary, models)),
    )

    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["5h", "Weekly"]
    assert [round(window.used_pct, 1) for window in snapshot.windows] == [40.0, 75.0]
    assert snapshot.plan is None


def test_shows_a_non_redundant_tier_name() -> None:
    summary = (FIXTURES / "antigravity_quota_summary.json").read_text(encoding="utf-8")
    models = (FIXTURES / "antigravity_models.json").read_text(encoding="utf-8")
    provider = AntigravityProvider(
        credential_reader=_reader(_credentials()),
        client=_client(
            _summary_handler(summary, models, tier_name="Gemini Code Assist Standard")
        ),
    )

    snapshot = provider.fetch()

    assert snapshot.plan == "Gemini Code Assist Standard"


def test_falls_back_to_model_quota_when_summary_is_empty() -> None:
    models = (FIXTURES / "antigravity_models.json").read_text(encoding="utf-8")
    provider = AntigravityProvider(
        credential_reader=_reader(_credentials()),
        client=_client(_summary_handler(json.dumps({"groups": []}), models)),
    )

    snapshot = provider.fetch()

    assert [window.label for window in snapshot.windows] == ["5h"]
    assert round(snapshot.windows[0].used_pct, 1) == 80.0


def test_auth_error_reports_expired() -> None:
    provider = AntigravityProvider(
        credential_reader=_reader(_credentials()),
        client=_client(lambda request: httpx2.Response(401)),
    )

    assert provider.fetch().status is ProviderStatus.EXPIRED


def test_network_error_reports_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom")

    provider = AntigravityProvider(
        credential_reader=_reader(_credentials()), client=_client(handler)
    )

    assert provider.fetch().status is ProviderStatus.ERROR


def test_scan_finds_client_id_and_secret() -> None:
    data = (
        b"junk\x00"
        + b"884354919052-abc.apps.googleusercontent.com"
        + b"\x00GOCSPX-abcdefghijklmnopqrstuvwxyz12\x00"
    )

    assert _scan_client_ids(data) == ["884354919052-abc.apps.googleusercontent.com"]
    assert _scan_client_secrets(data) == ["GOCSPX-abcdefghijklmnopqrstuvwxyz12"]


def test_refreshes_an_expired_token() -> None:
    summary = (FIXTURES / "antigravity_quota_summary.json").read_text(encoding="utf-8")
    models = (FIXTURES / "antigravity_models.json").read_text(encoding="utf-8")

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == "oauth2.googleapis.com":
            assert b"grant_type=refresh_token" in request.content
            return httpx2.Response(200, text=json.dumps({"access_token": "fresh"}))
        path = request.url.path
        if path.endswith("loadCodeAssist"):
            return httpx2.Response(
                200,
                text=json.dumps(
                    {
                        "cloudaicompanionProject": "proj-1",
                        "currentTier": {"name": "Antigravity"},
                    }
                ),
            )
        if path.endswith("retrieveUserQuotaSummary"):
            return httpx2.Response(200, text=summary)
        if path.endswith("fetchAvailableModels"):
            return httpx2.Response(200, text=models)
        return httpx2.Response(404)

    expired = json.dumps(
        {
            "token": {
                "access_token": "old",
                "refresh_token": "refresh",
                "expiry": "2000-01-01T00:00:00Z",
            }
        }
    ).encode("utf-8")

    provider = AntigravityProvider(
        credential_reader=_reader(expired),
        oauth_clients_provider=lambda: (("client-id", "client-secret"),),
        client=_client(handler),
    )

    snapshot = provider.fetch()

    assert snapshot.status is ProviderStatus.OK
    assert [window.label for window in snapshot.windows] == ["5h", "Weekly"]


def test_expired_token_without_refresh_reports_expired() -> None:
    expired = json.dumps(
        {"token": {"access_token": "old", "expiry": "2000-01-01T00:00:00Z"}}
    ).encode("utf-8")

    provider = AntigravityProvider(
        credential_reader=_reader(expired),
        client=_client(lambda request: httpx2.Response(401)),
    )

    assert provider.fetch().status is ProviderStatus.EXPIRED
