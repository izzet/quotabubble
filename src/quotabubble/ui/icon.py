from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def _pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.06
    body = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(22, 22, 26))
    painter.drawRoundedRect(body, size * 0.28, size * 0.28)

    ring = body.adjusted(size * 0.22, size * 0.22, -size * 0.22, -size * 0.22)
    pen = QPen(QColor(255, 255, 255, 55), size * 0.11)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    painter.setPen(pen)
    painter.drawArc(ring, 90 * 16, -360 * 16)
    pen.setColor(QColor(94, 197, 132))
    painter.setPen(pen)
    painter.drawArc(ring, 90 * 16, -252 * 16)

    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_pixmap(size))
    return icon
