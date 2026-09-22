from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.generated.design_tokens import TOKENS
from quotabubble.platform import configure_window
from quotabubble.presentation.builder import build_bubble_view
from quotabubble.presentation.models import AppearanceView, MetricView, ProviderView
from quotabubble.providers.base import UsageSnapshot
from quotabubble.ui.context_menu import build_context_menu
from quotabubble.ui.panel import (
    BAR_HEIGHT,
    PADDING,
    TEXT,
    TEXT_DIM,
    TONES,
    expanded_content_height,
    paint_expanded,
)


class BubbleWindow(QWidget):
    settings_requested = Signal()
    refresh_requested = Signal()

    COMPACT_WIDTH = TOKENS["size"]["compactWidth"]
    EXPANDED_WIDTH = TOKENS["size"]["expandedWidth"]
    COMPACT_ROW_HEIGHT = TOKENS["size"]["compactRowHeight"]
    NAME_GAP = TOKENS["size"]["nameGap"]
    MINI_LABEL_WIDTH = TOKENS["size"]["miniLabelWidth"]
    MINI_BAR_WIDTH = TOKENS["size"]["miniBarWidth"]
    MINI_PCT_WIDTH = TOKENS["size"]["miniPercentWidth"]
    MINI_GAP = TOKENS["size"]["miniGap"]
    GROUP_GAP = TOKENS["size"]["compactGroupGap"]
    CORNER_RADIUS = TOKENS["size"]["radius"]

    def __init__(self, state: AppState, settings: Settings) -> None:
        super().__init__()
        self._state = state
        self._settings = settings
        self._dragging = False
        self._pending_click = False
        self._press_pos = QPoint()
        self._drag_offset = QPoint()
        self._expanded = False
        self._expand_progress = 0.0

        self.setWindowTitle("QuotaBubble")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._resize_animation = QVariantAnimation(self)
        self._resize_animation.setDuration(150)
        self._resize_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._resize_animation.valueChanged.connect(self._on_resize_value)

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._fade_out)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(30_000)
        self._tick_timer.timeout.connect(self.update)

        self.setWindowOpacity(self._appearance().idle_opacity)
        self._apply_size()
        self._restore_position()
        configure_window(self)

    def sizeHint(self) -> QSize:
        return self._target_size()

    def refresh(self) -> None:
        self._apply_size()
        self.update()

    def apply_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._state.update(snapshot)
        self.refresh()

    def apply_settings(self) -> None:
        if not self.underMouse() and not self._dragging:
            self.setWindowOpacity(self._appearance().idle_opacity)
        self.refresh()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(TOKENS["color"]["border"]), 1))
        painter.setBrush(QColor(TOKENS["color"]["surface"]))
        painter.drawRoundedRect(background, self.CORNER_RADIUS, self.CORNER_RADIUS)

        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)

        view = self._view()
        if not view.providers:
            painter.setPen(TEXT_DIM)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No providers")
            return

        if self._expanded:
            paint_expanded(
                painter, view.providers, PADDING, self.width()
            )
            return

        top = PADDING
        for provider in view.providers:
            self._paint_compact_row(painter, provider, top)
            top += self.COMPACT_ROW_HEIGHT

    def _paint_compact_row(self, painter: QPainter, provider: ProviderView, top: int) -> None:
        left = PADDING
        right = self.width() - PADDING
        vertical = Qt.AlignmentFlag.AlignVCenter
        center = top + self.COMPACT_ROW_HEIGHT / 2

        painter.setPen(TEXT_DIM if provider.stale else TEXT)
        painter.drawText(
            QRectF(left, top, self._name_width(), self.COMPACT_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignLeft,
            provider.name,
        )

        metrics = provider.compact_metrics
        if not metrics:
            return
        if metrics[0].percent is None:
            painter.setPen(TEXT if metrics[0].detail is not None else TEXT_DIM)
            painter.drawText(
                QRectF(left, top, right - left, self.COMPACT_ROW_HEIGHT),
                vertical | Qt.AlignmentFlag.AlignRight,
                metrics[0].detail or metrics[0].label,
            )
            return

        group_width = self._group_width()
        second_left = right - group_width
        first_left = second_left - self.GROUP_GAP - group_width

        self._paint_mini(painter, metrics[0], first_left, top, center, provider.stale)
        if len(metrics) > 1 and metrics[1].percent is not None:
            self._paint_mini(painter, metrics[1], second_left, top, center, provider.stale)

    def _paint_mini(
        self,
        painter: QPainter,
        metric: MetricView,
        left: int,
        top: int,
        center: float,
        stale: bool,
    ) -> None:
        vertical = Qt.AlignmentFlag.AlignVCenter

        painter.setPen(TEXT_DIM)
        painter.drawText(
            QRectF(left, top, self.MINI_LABEL_WIDTH, self.COMPACT_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignRight,
            metric.compact_label or metric.label,
        )

        bar_left = left + self.MINI_LABEL_WIDTH + self.MINI_GAP
        bar_top = center - BAR_HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 34))
        painter.drawRoundedRect(
            QRectF(bar_left, bar_top, self.MINI_BAR_WIDTH, BAR_HEIGHT), 3, 3
        )

        fill = self.MINI_BAR_WIDTH * (metric.bar_fraction or 0)
        if fill > 0:
            painter.setBrush(TONES[metric.tone])
            painter.drawRoundedRect(QRectF(bar_left, bar_top, fill, BAR_HEIGHT), 3, 3)

        painter.setPen(TEXT_DIM if stale else TEXT)
        painter.drawText(
            QRectF(
                bar_left + self.MINI_BAR_WIDTH + self.MINI_GAP,
                top,
                self.MINI_PCT_WIDTH,
                self.COMPACT_ROW_HEIGHT,
            ),
            vertical | Qt.AlignmentFlag.AlignRight,
            f"{metric.percent}%",
        )

    @classmethod
    def _group_width(cls) -> int:
        return (
            cls.MINI_LABEL_WIDTH
            + cls.MINI_GAP
            + cls.MINI_BAR_WIDTH
            + cls.MINI_GAP
            + cls.MINI_PCT_WIDTH
        )

    def _content_font(self) -> QFont:
        font = QFont(self.font())
        font.setPointSize(9)
        return font

    def _name_width(self) -> int:
        providers = self._view().providers
        if not providers:
            return 0
        metrics = QFontMetrics(self._content_font())
        return max(metrics.horizontalAdvance(provider.name) for provider in providers)

    def _compact_width(self) -> int:
        groups = 2 * self._group_width() + self.GROUP_GAP
        needed = PADDING * 2 + self._name_width() + self.NAME_GAP + groups
        return max(self.COMPACT_WIDTH, needed)

    def enterEvent(self, event) -> None:
        self._fade_timer.stop()
        self._animate_opacity(self._appearance().hover_opacity)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._dragging and not self._expanded:
            self._fade_timer.start(self._appearance().fade_delay_ms)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._pending_click = True
            self._fade_timer.stop()
            self._animate_opacity(self._appearance().hover_opacity)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging or self._pending_click:
            if event.buttons() & Qt.MouseButton.LeftButton:
                if not self._dragging:
                    moved = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                    if moved >= QApplication.startDragDistance():
                        self._dragging = True
                        self._pending_click = False
                if self._dragging:
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
                    event.accept()
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            was_pending = self._pending_click
            self._dragging = False
            self._pending_click = False
            if was_dragging:
                self._settings.position = (self.x(), self.y())
                self._settings.save()
                if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                    self._fade_timer.start(self._appearance().fade_delay_ms)
                event.accept()
                return
            if was_pending:
                self._toggle_expanded()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = build_context_menu(self, self._request_settings, self._request_refresh)
        menu.exec(event.globalPos())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        configure_window(self)

    def event(self, event) -> bool:
        if event.type() in (
            QEvent.Type.ScreenChangeInternal,
            QEvent.Type.DevicePixelRatioChange,
        ):
            self._handle_screen_change()
        return super().event(event)

    def _request_settings(self) -> None:
        self.settings_requested.emit()

    def _request_refresh(self) -> None:
        self.refresh_requested.emit()

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._fade_timer.stop()
            self._tick_timer.start()
            self._animate_opacity(self._appearance().hover_opacity)
        else:
            self._tick_timer.stop()
            if not self.underMouse():
                self._fade_timer.start(self._appearance().fade_delay_ms)
        self._start_resize_animation()

    def _start_resize_animation(self) -> None:
        target = 1.0 if self._expanded else 0.0
        self._resize_animation.stop()
        self._resize_animation.setStartValue(self._expand_progress)
        self._resize_animation.setEndValue(target)
        self._resize_animation.start()

    def _on_resize_value(self, value: object) -> None:
        self._expand_progress = max(0.0, min(1.0, float(value)))
        compact = self._compact_size()
        expanded = self._expanded_size()
        width = compact.width() + (expanded.width() - compact.width()) * self._expand_progress
        height = compact.height() + (expanded.height() - compact.height()) * self._expand_progress
        self.setFixedSize(round(width), max(1, round(height)))
        if not self._dragging:
            self._clamp_to_screen()
        self.update()

    def _compact_size(self) -> QSize:
        rows = max(1, len(self._view().providers))
        return QSize(self._compact_width(), PADDING * 2 + rows * self.COMPACT_ROW_HEIGHT)

    def _expanded_size(self) -> QSize:
        providers = self._view().providers
        width = max(self.EXPANDED_WIDTH, self._compact_width())
        return QSize(width, PADDING * 2 + expanded_content_height(providers))

    def _view(self):
        return build_bubble_view(self._state.ordered(), self._settings)

    def _appearance(self) -> AppearanceView:
        return self._view().appearance

    def _target_size(self) -> QSize:
        return self._expanded_size() if self._expanded else self._compact_size()

    def _target_height(self) -> int:
        return self._target_size().height()

    def _apply_size(self) -> None:
        self._expand_progress = 1.0 if self._expanded else 0.0
        self.setFixedSize(self._target_size())

    def _handle_screen_change(self) -> None:
        self._apply_size()
        self.update()
        if not self._dragging:
            self._clamp_to_screen()

    def _clamp_to_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = min(max(self.x(), area.left()), area.right() - self.width())
        y = min(max(self.y(), area.top()), area.bottom() - self.height())
        self.move(x, y)

    def _fade_out(self) -> None:
        if not self._dragging and not self._expanded:
            self._animate_opacity(self._appearance().idle_opacity)

    def _animate_opacity(self, value: float) -> None:
        self._animation.stop()
        self._animation.setDuration(self._appearance().fade_duration_ms)
        self._animation.setStartValue(self.windowOpacity())
        self._animation.setEndValue(value)
        self._animation.start()

    def _available_geometry(self) -> QRect:
        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.availableGeometry())
        return geometry

    def _restore_position(self) -> None:
        target: QPoint | None = None
        if self._settings.position is not None:
            candidate = QPoint(self._settings.position[0], self._settings.position[1])
            if self._available_geometry().contains(candidate):
                target = candidate
        if target is None:
            screen = QGuiApplication.primaryScreen()
            area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
            target = QPoint(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
        self.move(target)
