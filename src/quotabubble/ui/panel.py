from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter

from quotabubble.presentation.generated_tokens import TOKENS
from quotabubble.presentation.models import MetricView, ProviderView

PADDING = TOKENS["size"]["padding"]
HEADER_ROW_HEIGHT = TOKENS["size"]["headerRowHeight"]
WINDOW_ROW_HEIGHT = TOKENS["size"]["metricRowHeight"]
PROVIDER_GAP = TOKENS["size"]["providerGap"]
BAR_HEIGHT = TOKENS["size"]["barHeight"]
LABEL_WIDTH = TOKENS["size"]["metricLabelWidth"]
BAR_WIDTH = TOKENS["size"]["metricBarWidth"]
PCT_WIDTH = TOKENS["size"]["metricPercentWidth"]
RESET_WIDTH = TOKENS["size"]["metricResetWidth"]

TEXT = QColor(TOKENS["color"]["text"])
TEXT_LABEL = QColor(205, 205, 215)
TEXT_DIM = QColor(TOKENS["color"]["textDim"])
BAR_TRACK = QColor(TOKENS["color"]["track"])
TONES = {
    "ok": QColor(TOKENS["color"]["ok"]),
    "warning": QColor(TOKENS["color"]["warning"]),
    "critical": QColor(TOKENS["color"]["critical"]),
    "muted": TEXT_DIM,
}


def expanded_content_height(providers: list[ProviderView]) -> int:
    return sum(
        HEADER_ROW_HEIGHT + len(provider.expanded_metrics) * WINDOW_ROW_HEIGHT
        + (PROVIDER_GAP if index < len(providers) - 1 else 0)
        for index, provider in enumerate(providers)
    )


def paint_expanded(
    painter: QPainter, providers: list[ProviderView], top: int, width: int
) -> None:
    left = PADDING
    right = width - PADDING
    vertical = Qt.AlignmentFlag.AlignVCenter
    base_font = painter.font()
    bold_font = QFont(base_font)
    bold_font.setBold(True)

    for provider in providers:
        y = top
        header = QRectF(left, y, right - left, HEADER_ROW_HEIGHT)
        painter.setFont(bold_font)
        painter.setPen(TEXT_DIM if provider.stale else TEXT)
        painter.drawText(header, vertical | Qt.AlignmentFlag.AlignLeft, provider.name)
        painter.setFont(base_font)
        if provider.trailing:
            painter.setPen(TEXT_DIM)
            painter.drawText(header, vertical | Qt.AlignmentFlag.AlignRight, provider.trailing)
        y += HEADER_ROW_HEIGHT
        for metric in provider.expanded_metrics:
            _paint_metric_row(painter, metric, y, left, right)
            y += WINDOW_ROW_HEIGHT
        top = y + PROVIDER_GAP


def _paint_metric_row(
    painter: QPainter, metric: MetricView, top: int, left: int, right: int
) -> None:
    vertical = Qt.AlignmentFlag.AlignVCenter
    painter.setPen(TEXT_LABEL)
    if metric.percent is None:
        painter.setPen(TEXT_LABEL if metric.detail is not None else TEXT_DIM)
        painter.drawText(
            QRectF(left, top, LABEL_WIDTH, WINDOW_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignLeft,
            metric.label,
        )
        if metric.detail is None:
            return
        painter.setPen(TEXT_DIM)
        painter.drawText(
            QRectF(left + LABEL_WIDTH, top, right - left - LABEL_WIDTH, WINDOW_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignLeft,
            metric.detail or "—",
        )
        return

    painter.drawText(
        QRectF(left, top, LABEL_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignLeft,
        metric.label,
    )

    bar_left = left + LABEL_WIDTH
    bar = QRectF(bar_left, top + (WINDOW_ROW_HEIGHT - BAR_HEIGHT) / 2, BAR_WIDTH, BAR_HEIGHT)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(BAR_TRACK)
    painter.drawRoundedRect(bar, 3, 3)
    fill = BAR_WIDTH * (metric.bar_fraction or 0)
    if fill:
        painter.setBrush(TONES[metric.tone])
        painter.drawRoundedRect(QRectF(bar_left, bar.top(), fill, BAR_HEIGHT), 3, 3)
    painter.setPen(TEXT)
    painter.drawText(
        QRectF(bar_left + BAR_WIDTH + 6, top, PCT_WIDTH, WINDOW_ROW_HEIGHT),
        vertical | Qt.AlignmentFlag.AlignRight,
        f"{metric.percent}%",
    )
    if metric.reset_text:
        painter.setPen(TEXT_DIM)
        painter.drawText(
            QRectF(right - RESET_WIDTH, top, RESET_WIDTH, WINDOW_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignRight,
            metric.reset_text,
        )
