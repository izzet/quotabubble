from __future__ import annotations

import json
from pathlib import Path

EXTENSION_DIR = Path(__file__).parents[1] / "gnome-shell-extension"
DBUS_SERVICE = (
    Path(__file__).parents[1] / "packaging" / "linux" / "dev.izzet.quotabubble.service"
)


def test_extension_metadata_declares_the_installed_uuid() -> None:
    metadata = json.loads((EXTENSION_DIR / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["uuid"] == "quotabubble@izzet.dev"
    assert metadata["shell-version"] == ["46"]


def test_extension_has_its_required_entrypoint() -> None:
    source = (EXTENSION_DIR / "extension.js").read_text(encoding="utf-8")

    assert "export default class QuotaBubbleExtension" in source
    assert "dev.izzet.quotabubble.Service1" in source
    assert "Main.layoutManager.addChrome" in source
    assert "_setExpanded" in source
    assert "_beginPointerAction" in source
    assert "Gio.DBusProxy.new_for_bus_finish" in source
    assert "proxy.call_finish" in source
    assert "BubbleRenderer" in source
    assert "Gio.bus_watch_name" in source
    assert "Settings…" in source
    assert "dev.izzet.QuotaBubbleSettings.desktop" in source
    assert "GLib.timeout_add" in source
    assert "fade_delay_ms" in source
    assert "fade_duration_ms" in source
    assert "NotificationRaised" in source
    assert "Main.notify" in source
    assert "_dbusSignalId" in source
    assert "this._actor.opacity = Math.round(opacity * 255)" in source
    assert "'g-signal'" in source
    assert "parameters.deepUnpack()" in source
    assert "AppearanceChanged" in source
    assert "connectSignal" not in source
    assert "_handleServiceSignal" in source


def test_extension_renderer_uses_the_presentation_contract() -> None:
    source = (EXTENSION_DIR / "renderer.js").read_text(encoding="utf-8")

    assert "St.DrawingArea" in source
    assert "expanded_metrics" in source
    assert "compact_metrics" in source
    assert "./generated/tokens.js" in source
    assert "Number.isInteger(metric.percent)" in source
    assert "size.miniPercentWidth" in source


def test_package_activates_the_extension_service_on_the_session_bus() -> None:
    payload = DBUS_SERVICE.read_text(encoding="utf-8")

    assert "Name=dev.izzet.quotabubble" in payload
    assert "Exec=/usr/lib/quotabubble/quotabubble-service" in payload


def test_linux_settings_desktop_entry_uses_the_settings_launcher() -> None:
    payload = (
        Path(__file__).parents[1]
        / "packaging"
        / "linux"
        / "dev.izzet.QuotaBubbleSettings.desktop"
    ).read_text(encoding="utf-8")

    assert "Exec=quotabubble-settings" in payload
