from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_SCRIPT = Path(__file__).parents[1] / "packaging/linux/package_deb.py"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="Debian packaging is Linux only",
)


def _package_module() -> object:
    spec = importlib.util.spec_from_file_location("package_deb", PACKAGE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_debian_package_contains_the_native_gnome_installation(tmp_path: Path) -> None:
    source = tmp_path / "dist"
    source.mkdir()
    for name in ("quotabubble-service", "quotabubble-settings"):
        executable = source / name
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        executable.chmod(0o755)
    package = tmp_path / "quotabubble.deb"

    module = _package_module()
    module.build_package(source, package, "0.0.0-test")

    fields = subprocess.run(
        ["dpkg-deb", "--field", str(package), "Package", "Version", "Architecture"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    contents = subprocess.run(
        ["dpkg-deb", "--contents", str(package)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "Package: quotabubble" in fields
    assert "Version: 0.0.0-test" in fields
    assert "Architecture: amd64" in fields
    assert "usr/lib/quotabubble/quotabubble-service" in contents
    assert "usr/lib/quotabubble/quotabubble-settings" in contents
    assert "usr/share/dbus-1/services/dev.izzet.quotabubble.service" in contents
    assert "usr/share/gnome-shell/extensions/quotabubble@izzet.dev/extension.js" in contents
    assert "usr/share/applications/dev.izzet.QuotaBubbleSettings.desktop" in contents
    assert "usr/share/icons/hicolor/scalable/apps/dev.izzet.QuotaBubble.svg" in contents
