from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer
from PySide6.QtGui import QGuiApplication

from quotabubble.ui.icon import _pixmap

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_IMAGES = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)


def _png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    _pixmap(size).toImage().save(buffer, "PNG")
    return bytes(buffer.data())


def build_ico(path: Path) -> None:
    images = [(size, _png_bytes(size)) for size in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    data = b""
    for size, blob in images:
        dimension = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + data)


def build_icns(path: Path) -> None:
    """Build a macOS icon with the PNG layout expected by ``iconutil``."""
    with tempfile.TemporaryDirectory(prefix="quotabubble-icon-") as temporary:
        iconset = Path(temporary) / "QuotaBubble.iconset"
        iconset.mkdir()
        for size, name in ICNS_IMAGES:
            (iconset / name).write_bytes(_png_bytes(size))
        subprocess.run(
            ["iconutil", "--convert", "icns", "--output", str(path), str(iconset)],
            check=True,
        )


def main() -> None:
    QGuiApplication([])
    assets = Path(__file__).resolve().parent.parent / "assets"
    ico_target = assets / "quotabubble.ico"
    build_ico(ico_target)
    print(f"wrote {ico_target}")
    if sys.platform == "darwin":
        icns_target = assets / "quotabubble.icns"
        build_icns(icns_target)
        print(f"wrote {icns_target}")


if __name__ == "__main__":
    main()
