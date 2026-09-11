from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from quotabubble.app.settings import Settings
from quotabubble.providers.base import Credits, ProviderStatus, UsageSnapshot, UsageWindow
from quotabubble.ui.formatting import format_reset

PADDING = 12
HEADER_ROW_HEIGHT = 20
WINDOW_ROW_HEIGHT = 22
PROVIDER_GAP = 6
BAR_HEIGHT = 6
LABEL_WIDTH = 60
BAR_WIDTH = 100
PCT_WIDTH = 42
RESET_WIDTH = 64

TEXT = QColor(235, 235, 240)
TEXT_LABEL = QColor(205, 205, 215)
TEXT_DIM = QColor(150, 150, 160)
BAR_TRACK = QColor(255, 255, 255, 34)
COLOR_LOW = QColor(94, 197, 132)
COLOR_MID = QColor(232, 176, 74)
COLOR_HIGH = QColor(232, 92, 84)


def bar_color(used_pct: float) -> QColor:
    if used_pct >= 85:
        return COLOR_HIGH
    if used_pct >= 60:
        return COLOR_MID
    return COLOR_LOW


def row_color(window: UsageWindow) -> QColor:
    if window.severity == "critical":
        return COLOR_HIGH
    return bar_color(window.used_pct)


def display_pct(used_pct: float, settings: Settings) -> float:
    return (100.0 - used_pct) if settings.show_remaining else used_pct


def status_text(snapshot: UsageSnapshot) -> str:
    if snapshot.status is ProviderStatus.OK:
        return "—"
    if snapshot.status is ProviderStatus.LOADING:
        return "..."
    if snapshot.status is ProviderStatus.NO_CREDENTIALS:
        return "sign in"
    if snapshot.status is ProviderStatus.EXPIRED:
        return "expired"
    return "error"


def _content_rows(snapshot: UsageSnapshot) -> int:
    if snapshot.status is not ProviderStatus.OK:
        return 1
    if snapshot.windows:
        return len(snapshot.windows)
    if snapshot.credits is None:
        return 1
    return 0


def expanded_content_height(snapshots: list[UsageSnapshot]) -> int:
    height = 0
    for index, snapshot in enumerate(snapshots):
        height += HEADER_ROW_HEIGHT + _content_rows(snapshot) * WINDOW_ROW_HEIGHT
        if snapshot.credits is not None:
            height += WINDOW_ROW_HEIGHT
        if index < len(snapshots) - 1:
            height += PROVIDER_GAP
    return height


def paint_expanded(
    painter: QPainter,
    snapshots: list[UsageSnapshot],
    settings: Settings,
    top: int,
    width: int,
) -> None:
    left = PADDING
    right = width - PADDING
    vertical = Qt.AlignmentFlag.AlignVCenter

    for snapshot in snapshots:
        y = top
        header = QRectF(left, y, right - left, HEADER_ROW_HEIGHT)
        painter.setPen(TEXT)
        painter.drawText(header, vertical | Qt.AlignmentFlag.AlignLeft, snapshot.display_name)
        if snapshot.plan:
            painter.setPen(TEXT_DIM)
            painter.drawText(header, vertical | Qt.AlignmentFlag.AlignRight, snapshot.plan)
        y += HEADER_ROW_HEIGHT

        if snapshot.status is not ProviderStatus.OK:
            painter.setPen(TEXT_DIM)
            row = QRectF(left, y, right - left, WINDOW_ROW_HEIGHT)
            painter.drawText(row, vertical | Qt.AlignmentFlag.AlignLeft, status_text(snapshot))
            y += WINDOW_ROW_HEIGHT
        elif snapshot.windows:
            for window in snapshot.windows:
                _paint_window_row(painter, window, settings, y, left, right)
                y += WINDOW_ROW_HEIGHT
        elif snapshot.credits is None:
            painter.setPen(TEXT_DIM)
            row = QRectF(left, y, right - left, WINDOW_ROW_HEIGHT)
            painter.drawText(row, vertical | Qt.AlignmentFlag.AlignLeft, "—")
            y += WINDOW_ROW_HEIGHT

        if snapshot.credits is not None:
            _paint_credits_row(painter, snapshot.credits, y, left, right)
            y += WINDOW_ROW_HEIGHT

        top = y + PROVIDER_GAP


def _paint_window_row(
    painter: QPainter,
    window: UsageWindow,
    settings: Settings,
    top: int,
    left: int,
    right: int,
) -> None:
    vertical = Qt.AlignmentFlag.AlignVCenter

    painter.setPen(TEXT_LABEL)
    painter.drawText(
        QRectF(left, top, LABEL_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignLeft,
        window.label,
    )

    bar_left = left + LABEL_WIDTH
    bar = QRectF(bar_left, top + (WINDOW_ROW_HEIGHT - BAR_HEIGHT) / 2, BAR_WIDTH, BAR_HEIGHT)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(BAR_TRACK)
    painter.drawRoundedRect(bar, 3, 3)

    shown = display_pct(window.used_pct, settings)
    fill = BAR_WIDTH * max(0.0, min(1.0, shown / 100.0))
    if fill > 0:
        painter.setBrush(row_color(window))
        painter.drawRoundedRect(QRectF(bar_left, bar.top(), fill, BAR_HEIGHT), 3, 3)

    painter.setPen(TEXT)
    painter.drawText(
        QRectF(bar_left + BAR_WIDTH + 6, top, PCT_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignRight,
        f"{shown:.0f}%",
    )

    reset = format_reset(window.resets_at)
    if reset:
        painter.setPen(TEXT_DIM)
        painter.drawText(
            QRectF(right - RESET_WIDTH, top, RESET_WIDTH, WINDOW_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignRight,
            reset,
        )


def _paint_credits_row(
    painter: QPainter,
    credits: Credits,
    top: int,
    left: int,
    right: int,
) -> None:
    vertical = Qt.AlignmentFlag.AlignVCenter
    painter.setPen(TEXT_LABEL)
    painter.drawText(
        QRectF(left, top, LABEL_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignLeft,
        "Credits",
    )
    painter.setPen(TEXT_DIM)
    painter.drawText(
        QRectF(left + LABEL_WIDTH, top, right - left - LABEL_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignLeft,
        credits.display,
    )
