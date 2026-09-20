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


def test_package_activates_the_extension_service_on_the_session_bus() -> None:
    payload = DBUS_SERVICE.read_text(encoding="utf-8")

    assert "Name=dev.izzet.quotabubble" in payload
    assert "Exec=/usr/lib/quotabubble/quotabubble-service" in payload
