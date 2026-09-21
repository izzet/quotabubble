from __future__ import annotations

from quotabubble.credentials import copilot


def test_read_copilot_cli_credentials_uses_the_active_user_and_keyring(
    monkeypatch, tmp_path
) -> None:
    home = tmp_path / "copilot"
    home.mkdir()
    (home / "config.json").write_text(
        '// managed by Copilot\n{"lastLoggedInUser":{"host":"github.com","login":"izzet"}}'
    )
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.setattr(copilot.sys, "platform", "linux")
    seen: list[str] = []
    monkeypatch.setattr(
        copilot,
        "read_generic_credential",
        lambda target: seen.append(target) or b"token",
    )

    assert copilot.read_copilot_cli_credentials() == [
        ("copilot-cli:https://github.com:izzet", b"token")
    ]
    assert seen == ["copilot-cli:https://github.com:izzet"]


def test_read_copilot_cli_credentials_requires_a_signed_in_user(monkeypatch, tmp_path) -> None:
    home = tmp_path / "copilot"
    home.mkdir()
    (home / "config.json").write_text("{}")
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.setattr(copilot.sys, "platform", "linux")

    assert copilot.read_copilot_cli_credentials() == []
