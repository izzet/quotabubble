from __future__ import annotations

import json
from pathlib import Path

import pytest

from quotabubble.credentials.kimi import (
    KimiCodeLogin,
    kimi_code_base_url,
    kimi_code_device_id,
    kimi_code_home,
    read_kimi_code_login,
)


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / ".kimi-code"
    (directory / "credentials").mkdir(parents=True)
    monkeypatch.setenv("KIMI_CODE_HOME", str(directory))
    monkeypatch.delenv("KIMI_CODE_BASE_URL", raising=False)
    return directory


def _write(home: Path, name: str, payload: object) -> Path:
    path = home / "credentials" / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_home_defaults_to_dot_kimi_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIMI_CODE_HOME")

    assert kimi_code_home() == Path.home() / ".kimi-code"


def test_reads_the_login_named_by_the_cli_config(home: Path) -> None:
    (home / "config.toml").write_text(
        '[providers."managed:kimi-code".oauth]\nkey = "oauth/kimi-code-env-abc"\n',
        encoding="utf-8",
    )
    _write(home, "kimi-code.json", {"access_token": "other"})
    _write(home, "kimi-code-env-abc.json", {"access_token": "mine", "expires_at": 2000})

    assert read_kimi_code_login() == KimiCodeLogin("mine", "", 2000.0)


def test_falls_back_to_kimi_code_json_then_any_credential(home: Path) -> None:
    _write(home, "anything.json", {"refresh_token": "refresh-only"})
    assert read_kimi_code_login() == KimiCodeLogin("", "refresh-only", None)

    _write(home, "kimi-code.json", {"access_token": "acc", "refresh_token": "ref"})
    assert read_kimi_code_login() == KimiCodeLogin("acc", "ref", None)


def test_unusable_credentials_are_ignored(home: Path) -> None:
    assert read_kimi_code_login() is None
    (home / "credentials" / "bad.json").write_text("not json", encoding="utf-8")
    _write(home, "list.json", ["nope"])
    _write(home, "empty.json", {"access_token": "  ", "refresh_token": 5})

    assert read_kimi_code_login() is None


def test_missing_credentials_directory_is_tolerated(home: Path) -> None:
    (home / "credentials").rmdir()

    assert read_kimi_code_login() is None


def test_non_numeric_expiry_is_treated_as_unknown(home: Path) -> None:
    _write(home, "kimi-code.json", {"access_token": "a", "expires_at": True})

    assert read_kimi_code_login() == KimiCodeLogin("a", "", None)


def test_freshness_requires_a_token_and_a_future_expiry_beyond_the_skew() -> None:
    assert KimiCodeLogin("a", "", 1000.0).is_fresh(now=900.0) is True
    assert KimiCodeLogin("a", "", 950.0).is_fresh(now=900.0) is False
    assert KimiCodeLogin("a", "", None).is_fresh(now=0.0) is False
    assert KimiCodeLogin("", "r", 10_000.0).is_fresh(now=0.0) is False


def test_base_url_prefers_env_then_config_then_oauth_host(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert kimi_code_base_url() is None

    (home / "config.toml").write_text(
        """
[providers."managed:kimi-code".oauth]
oauth_host = "https://auth.kimi.ai"
""",
        encoding="utf-8",
    )
    assert kimi_code_base_url() == "https://api.kimi.ai"

    (home / "config.toml").write_text(
        """
[providers."managed:kimi-code"]
base_url = "https://api.kimi.com/coding/v1"

[providers."managed:kimi-code".oauth]
oauth_host = "https://auth.kimi.ai"
""",
        encoding="utf-8",
    )
    assert kimi_code_base_url() == "https://api.kimi.com/coding/v1"

    monkeypatch.setenv("KIMI_CODE_BASE_URL", " https://example.test ")
    assert kimi_code_base_url() == "https://example.test"


def test_unrecognised_oauth_host_gives_no_base_url(home: Path) -> None:
    (home / "config.toml").write_text(
        """
[providers."managed:kimi-code".oauth]
oauth_host = "https://login.example"
""",
        encoding="utf-8",
    )

    assert kimi_code_base_url() is None


def test_invalid_config_gives_no_base_url(home: Path) -> None:
    (home / "config.toml").write_text("this is [not valid toml", encoding="utf-8")

    assert kimi_code_base_url() is None


def test_device_id_uses_the_cli_file_or_a_throwaway_without_writing(home: Path) -> None:
    generated = kimi_code_device_id()
    assert generated and not (home / "device_id").exists()

    (home / "device_id").write_text("device-123\n", encoding="utf-8")
    assert kimi_code_device_id() == "device-123"
