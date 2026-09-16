from __future__ import annotations

import json
from pathlib import Path

from quotabubble.credentials.opencode import (
    default_opencode_auth_paths,
    default_opencode_config_paths,
    read_opencode_api_key_from_auth_file,
    read_opencode_api_key_from_config_file,
    resolve_opencode_api_key,
)


def test_default_paths_contain_standard_locations() -> None:
    auth_paths = default_opencode_auth_paths()
    assert any("auth.json" in str(p) for p in auth_paths)

    config_paths = default_opencode_config_paths()
    assert any("opencode.json" in str(p) for p in config_paths)


def test_read_opencode_api_key_from_auth_file(tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps({"opencode-go": {"key": "go_secret_123"}}), encoding="utf-8"
    )
    assert read_opencode_api_key_from_auth_file(auth_file) == "go_secret_123"

    auth_file.write_text(json.dumps({"opencode": "direct_key"}), encoding="utf-8")
    assert read_opencode_api_key_from_auth_file(auth_file) == "direct_key"


def test_read_opencode_api_key_from_auth_file_malformed(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")
    assert read_opencode_api_key_from_auth_file(bad_file) is None

    empty_dict_file = tmp_path / "empty.json"
    empty_dict_file.write_text("{}", encoding="utf-8")
    assert read_opencode_api_key_from_auth_file(empty_dict_file) is None


def test_read_opencode_api_key_from_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "opencode.jsonc"
    config_file.write_text(
        """
        {
          // OpenCode configuration
          "provider": {
            "opencode": {
              "options": {
                "apiKey": "from_provider_options"
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )
    assert read_opencode_api_key_from_config_file(config_file) == "from_provider_options"


def test_read_opencode_api_key_from_config_file_malformed(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.jsonc"
    bad_file.write_text("not json", encoding="utf-8")
    assert read_opencode_api_key_from_config_file(bad_file) is None


def test_resolve_opencode_api_key_precedence(tmp_path: Path, monkeypatch) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps({"opencode": {"key": "from_auth"}}), encoding="utf-8")

    config_file = tmp_path / "opencode.json"
    config_file.write_text(json.dumps({"apiKey": "from_config"}), encoding="utf-8")

    # 1. Explicit arg wins over all
    monkeypatch.setenv("OPENCODE_API_KEY", "from_env")
    assert (
        resolve_opencode_api_key(
            "from_arg", auth_paths=[auth_file], config_paths=[config_file]
        )
        == "from_arg"
    )

    # 2. Env wins over files
    assert (
        resolve_opencode_api_key(auth_paths=[auth_file], config_paths=[config_file])
        == "from_env"
    )

    # 3. Auth file wins over config file
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert (
        resolve_opencode_api_key(auth_paths=[auth_file], config_paths=[config_file])
        == "from_auth"
    )

    # 4. Config file wins when auth missing
    assert (
        resolve_opencode_api_key(auth_paths=[], config_paths=[config_file])
        == "from_config"
    )

    # 5. None when neither exists
    assert resolve_opencode_api_key(auth_paths=[], config_paths=[]) is None
