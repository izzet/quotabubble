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
    QGuiApplication,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.platform import configure_window
from quotabubble.providers.base import ProviderStatus, UsageSnapshot, UsageWindow
from quotabubble.ui.context_menu import build_context_menu
from quotabubble.ui.panel import (
    BAR_HEIGHT,
    PADDING,
    TEXT,
    TEXT_DIM,
    display_pct,
    expanded_content_height,
    paint_expanded,
    row_color,
    status_text,
)


class BubbleWindow(QWidget):
    settings_requested = Signal()

    COMPACT_WIDTH = 260
    EXPANDED_WIDTH = 300
    COMPACT_ROW_HEIGHT = 26
    NAME_WIDTH = 54
    MINI_LABEL_WIDTH = 18
    MINI_BAR_WIDTH = 32
    MINI_PCT_WIDTH = 26
    MINI_GAP = 4
    GROUP_GAP = 8
    CORNER_RADIUS = 14

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

        self.setWindowOpacity(self._settings.idle_opacity)
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
            self.setWindowOpacity(self._settings.idle_opacity)
        self.refresh()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QColor(22, 22, 26, 235))
        painter.drawRoundedRect(background, self.CORNER_RADIUS, self.CORNER_RADIUS)

        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)

        snapshots = self._state.ordered()
        if not snapshots:
            painter.setPen(TEXT_DIM)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No providers")
            return

        if self._expanded:
            paint_expanded(
                painter, snapshots, self._settings, PADDING, self.EXPANDED_WIDTH
            )
            return

        top = PADDING
        for snapshot in snapshots:
            self._paint_compact_row(painter, snapshot, top)
            top += self.COMPACT_ROW_HEIGHT

    def _paint_compact_row(self, painter: QPainter, snapshot: UsageSnapshot, top: int) -> None:
        left = PADDING
        right = self.width() - PADDING
        vertical = Qt.AlignmentFlag.AlignVCenter
        center = top + self.COMPACT_ROW_HEIGHT / 2

        painter.setPen(TEXT)
        painter.drawText(
            QRectF(left, top, self.NAME_WIDTH, self.COMPACT_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignLeft,
            snapshot.display_name,
        )

        if snapshot.status is not ProviderStatus.OK or not snapshot.windows:
            painter.setPen(TEXT_DIM)
            text = status_text(snapshot) if snapshot.status is not ProviderStatus.OK else "—"
            painter.drawText(
                QRectF(left, top, right - left, self.COMPACT_ROW_HEIGHT),
                vertical | Qt.AlignmentFlag.AlignRight,
                text,
            )
            return

        group_width = self._group_width()
        second_left = right - group_width
        first_left = second_left - self.GROUP_GAP - group_width

        self._paint_mini(painter, "5h", self._find(snapshot, "session"), first_left, top, center)
        self._paint_mini(painter, "wk", self._find(snapshot, "weekly"), second_left, top, center)

    def _paint_mini(
        self,
        painter: QPainter,
        label: str,
        window: UsageWindow | None,
        left: int,
        top: int,
        center: float,
    ) -> None:
        if window is None:
            return
        vertical = Qt.AlignmentFlag.AlignVCenter

        painter.setPen(TEXT_DIM)
        painter.drawText(
            QRectF(left, top, self.MINI_LABEL_WIDTH, self.COMPACT_ROW_HEIGHT),
            vertical | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        bar_left = left + self.MINI_LABEL_WIDTH + self.MINI_GAP
        bar_top = center - BAR_HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 34))
        painter.drawRoundedRect(
            QRectF(bar_left, bar_top, self.MINI_BAR_WIDTH, BAR_HEIGHT), 3, 3
        )

        shown = display_pct(window.used_pct, self._settings)
        fill = self.MINI_BAR_WIDTH * max(0.0, min(1.0, shown / 100.0))
        if fill > 0:
            painter.setBrush(row_color(window))
            painter.drawRoundedRect(QRectF(bar_left, bar_top, fill, BAR_HEIGHT), 3, 3)

        painter.setPen(TEXT)
        painter.drawText(
            QRectF(
                bar_left + self.MINI_BAR_WIDTH + self.MINI_GAP,
                top,
                self.MINI_PCT_WIDTH,
                self.COMPACT_ROW_HEIGHT,
            ),
            vertical | Qt.AlignmentFlag.AlignRight,
            f"{shown:.0f}%",
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

    @staticmethod
    def _find(snapshot: UsageSnapshot, key: str) -> UsageWindow | None:
        for window in snapshot.windows:
            if window.key == key:
                return window
        return None

    def enterEvent(self, event) -> None:
        self._fade_timer.stop()
        self._animate_opacity(self._settings.hover_opacity)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._dragging and not self._expanded:
            self._fade_timer.start(self._settings.fade_delay_ms)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._pending_click = True
            self._fade_timer.stop()
            self._animate_opacity(self._settings.hover_opacity)
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
                    self._fade_timer.start(self._settings.fade_delay_ms)
                event.accept()
                return
            if was_pending:
                self._toggle_expanded()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = build_context_menu(self, self._request_settings)
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

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._fade_timer.stop()
            self._animate_opacity(self._settings.hover_opacity)
        elif not self.underMouse():
            self._fade_timer.start(self._settings.fade_delay_ms)
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
        rows = max(1, len(self._state.ordered()))
        return QSize(self.COMPACT_WIDTH, PADDING * 2 + rows * self.COMPACT_ROW_HEIGHT)

    def _expanded_size(self) -> QSize:
        snapshots = self._state.ordered()
        return QSize(self.EXPANDED_WIDTH, PADDING * 2 + expanded_content_height(snapshots))

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
            self._animate_opacity(self._settings.idle_opacity)

    def _animate_opacity(self, value: float) -> None:
        self._animation.stop()
        self._animation.setDuration(self._settings.fade_duration_ms)
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
