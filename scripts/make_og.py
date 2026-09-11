from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QPainter,
    QPixmap,
    QRadialGradient,
)

from quotabubble.ui.icon import _pixmap

WIDTH, HEIGHT = 1200, 630
ROOT = Path(__file__).resolve().parent.parent


def build() -> None:
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor("#0e0e11"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    glow = QRadialGradient(QPointF(WIDTH * 0.18, -40), WIDTH * 0.9)
    glow.setColorAt(0.0, QColor(94, 197, 132, 80))
    glow.setColorAt(1.0, QColor(94, 197, 132, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawRect(0, 0, WIDTH, HEIGHT)

    painter.drawPixmap(80, 88, _pixmap(96))

    painter.setPen(QColor("#ececf1"))
    title = QFont("Segoe UI", 54)
    title.setBold(True)
    painter.setFont(title)
    painter.drawText(200, 152, "QuotaBubble")

    painter.setPen(QColor("#9a9aa5"))
    painter.setFont(QFont("Segoe UI", 24))
    painter.drawText(204, 198, "Your AI usage limits, always in sight.")

    shot = QPixmap(str(ROOT / "assets" / "screenshot-expanded.png"))
    if not shot.isNull():
        scaled = shot.scaledToHeight(
            int(HEIGHT * 0.5), Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(WIDTH - scaled.width() - 80, (HEIGHT - scaled.height()) // 2, scaled)

    painter.setPen(QColor("#6f6f79"))
    painter.setFont(QFont("Segoe UI", 18))
    painter.drawText(82, HEIGHT - 60, "izzet.github.io/quotabubble")
    painter.end()

    for target in (ROOT / "assets" / "og.png", ROOT / "website" / "public" / "og.png"):
        image.save(str(target))
        print(f"wrote {target}")


if __name__ == "__main__":
    QGuiApplication([])
    build()
