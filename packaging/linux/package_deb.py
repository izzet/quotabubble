from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from tomllib import loads

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_NAME = "quotabubble"
LIBRARY_DIR = Path("usr/lib") / PACKAGE_NAME
EXTENSION_DIR = Path("usr/share/gnome-shell/extensions/quotabubble@izzet.dev")


def package_version() -> str:
    data = loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def control_file(version: str) -> str:
    return f"""Package: {PACKAGE_NAME}
Version: {version}
Section: utils
Priority: optional
Architecture: amd64
Depends: libegl1, libglib2.0-0, libgl1, libxkbcommon0
Maintainer: Izzet Yildirim <izzet@izzet.dev>
Description: Desktop AI coding quota monitor for GNOME
 QuotaBubble displays coding-agent usage quotas through a native GNOME Shell extension.
"""


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True)


def build_package(source: Path, output: Path, version: str) -> None:
    if not source.is_dir():
        raise ValueError(f"missing PyInstaller output: {source}")
    with tempfile.TemporaryDirectory(prefix="quotabubble-deb-") as temporary:
        root = Path(temporary) / PACKAGE_NAME
        library = root / LIBRARY_DIR
        library.parent.mkdir(parents=True)
        copy_tree(source, library)

        bin_dir = root / "usr/bin"
        bin_dir.mkdir(parents=True)
        for executable in ("quotabubble-service", "quotabubble-settings"):
            (bin_dir / executable).symlink_to(Path("../lib") / PACKAGE_NAME / executable)

        share = root / "usr/share"
        copy_tree(PROJECT_ROOT / "gnome-shell-extension", root / EXTENSION_DIR)
        (share / "dbus-1/services").mkdir(parents=True)
        (share / "applications").mkdir(parents=True)
        shutil.copy2(
            PROJECT_ROOT / "packaging/linux/dev.izzet.quotabubble.service",
            share / "dbus-1/services/dev.izzet.quotabubble.service",
        )
        shutil.copy2(
            PROJECT_ROOT / "packaging/linux/dev.izzet.QuotaBubbleSettings.desktop",
            share / "applications/dev.izzet.QuotaBubbleSettings.desktop",
        )
        icon = share / "icons/hicolor/scalable/apps/dev.izzet.QuotaBubble.svg"
        icon.parent.mkdir(parents=True)
        shutil.copy2(PROJECT_ROOT / "assets/quotabubble.svg", icon)

        debian = root / "DEBIAN"
        debian.mkdir()
        (debian / "control").write_text(control_file(version), encoding="utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(root), str(output)],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the QuotaBubble Debian package")
    parser.add_argument("--source", type=Path, required=True, help="PyInstaller output directory")
    parser.add_argument("--output", type=Path, required=True, help="Debian package output path")
    parser.add_argument("--version", default=package_version())
    args = parser.parse_args()
    build_package(args.source, args.output, args.version)


if __name__ == "__main__":
    main()
