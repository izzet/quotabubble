from pathlib import Path

from quotabubble.app.settings import CONFIG_DIR, Settings, default_settings_path


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    Settings(idle_opacity=0.2, position=(120, 340)).save(path)
    loaded = Settings.load(path)

    assert loaded.idle_opacity == 0.2
    assert loaded.position == (120, 340)


def test_settings_load_missing_returns_defaults(tmp_path: Path) -> None:
    loaded = Settings.load(tmp_path / "absent.json")

    assert loaded.idle_opacity == 0.25
    assert loaded.refresh_interval_ms == 300_000
    assert loaded.position is None


def test_config_dir_is_not_doubled() -> None:
    assert CONFIG_DIR.name == "quotabubble"
    assert CONFIG_DIR.parent.name != "quotabubble"
    assert default_settings_path().name == "settings.json"
