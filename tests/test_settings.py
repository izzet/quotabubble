from pathlib import Path

import pytest

from quotabubble.app.settings import (
    CONFIG_DIR,
    Settings,
    default_settings_path,
    format_thresholds,
    parse_thresholds,
)


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    Settings(
        idle_opacity=0.2,
        position=(120, 340),
        notify_usage=False,
        notify_status=True,
        thresholds=[80, 95],
        provider_thresholds={"claude": [90]},
        history_enabled=True,
    ).save(path)
    loaded = Settings.load(path)

    assert loaded.idle_opacity == 0.2
    assert loaded.position == (120, 340)
    assert loaded.notify_usage is False
    assert loaded.notify_status is True
    assert loaded.thresholds == [80, 95]
    assert loaded.provider_thresholds == {"claude": [90]}
    assert loaded.history_enabled is True


def test_settings_load_missing_returns_defaults(tmp_path: Path) -> None:
    loaded = Settings.load(tmp_path / "absent.json")

    assert loaded.idle_opacity == 0.25
    assert loaded.refresh_interval_ms == 300_000
    assert loaded.position is None
    assert loaded.notify_usage is True
    assert loaded.notify_status is True
    assert loaded.thresholds == [75, 90]
    assert loaded.provider_thresholds == {}
    assert loaded.history_enabled is False


def test_settings_load_invalid_schema_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"idle_opacity": "not-a-number"}', encoding="utf-8")

    loaded = Settings.load(path)

    assert loaded.idle_opacity == 0.25


def test_config_dir_is_not_doubled() -> None:
    assert CONFIG_DIR.name == "quotabubble"
    assert CONFIG_DIR.parent.name != "quotabubble"
    assert default_settings_path().name == "settings.json"


def test_parse_thresholds() -> None:
    assert parse_thresholds("75, 90") == [75, 90]
    assert parse_thresholds(" 90 , 75 , 90 ") == [75, 90]
    assert parse_thresholds("50 80") == [50, 80]
    assert parse_thresholds("") == []
    assert parse_thresholds(None) == [75, 90]
    assert parse_thresholds([90, 75]) == [75, 90]

    with pytest.raises(ValueError):
        parse_thresholds("invalid")
    with pytest.raises(ValueError):
        parse_thresholds("0")
    with pytest.raises(ValueError):
        parse_thresholds("101")
    with pytest.raises(ValueError):
        parse_thresholds("-10")


def test_format_thresholds() -> None:
    assert format_thresholds([75, 90]) == "75, 90"
    assert format_thresholds([90, 75, 90]) == "75, 90"
    assert format_thresholds([]) == ""


def test_effective_thresholds() -> None:
    settings = Settings(
        thresholds=[75, 90],
        provider_thresholds={"claude": [80, 95]},
    )
    assert settings.effective_thresholds("claude") == [80, 95]
    assert settings.effective_thresholds("copilot") == [75, 90]
