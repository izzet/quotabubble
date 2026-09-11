from __future__ import annotations

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer
from PySide6.QtGui import QGuiApplication

from quotabubble.ui.icon import _pixmap

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    _pixmap(size).toImage().save(buffer, "PNG")
    return bytes(buffer.data())


def build_ico(path: Path) -> None:
    images = [(size, _png_bytes(size)) for size in SIZES]
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


def main() -> None:
    QGuiApplication([])
    target = Path(__file__).resolve().parent.parent / "assets" / "quotabubble.ico"
    build_ico(target)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
