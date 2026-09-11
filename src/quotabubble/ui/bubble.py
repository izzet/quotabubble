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
from PySide6.QtWidgets import QWidget

from quotabubble.app.settings import Settings
from quotabubble.app.state import AppState
from quotabubble.platform import configure_window
from quotabubble.providers.base import ProviderStatus, UsageSnapshot
from quotabubble.ui.context_menu import build_context_menu


class BubbleWindow(QWidget):
    ROW_HEIGHT = 24
    PADDING = 12
    BAR_WIDTH = 44
    BAR_HEIGHT = 6
    MIN_WIDTH = 168
    CORNER_RADIUS = 14

    def __init__(self, state: AppState, settings: Settings) -> None:
        super().__init__()
        self._state = state
        self._settings = settings
        self._dragging = False
        self._drag_offset = QPoint()

        self.setWindowTitle("QuotaBubble")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._fade_out)

        self.setWindowOpacity(self._settings.idle_opacity)
        self.setFixedSize(self.sizeHint())
        self._restore_position()
        configure_window(self)

    def sizeHint(self) -> QSize:
        rows = max(1, len(self._state.ordered()))
        height = self.PADDING * 2 + rows * self.ROW_HEIGHT
        return QSize(self.MIN_WIDTH, height)

    def refresh(self) -> None:
        self.setFixedSize(self.sizeHint())
        self.update()

    def apply_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._state.update(snapshot)
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
            painter.setPen(QColor(180, 180, 190))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No providers")
            return

        top = self.PADDING
        for snapshot in snapshots:
            self._paint_row(painter, snapshot, top)
            top += self.ROW_HEIGHT

    def _paint_row(self, painter: QPainter, snapshot: UsageSnapshot, top: int) -> None:
        left = self.PADDING
        right = self.width() - self.PADDING
        row = QRectF(left, top, right - left, self.ROW_HEIGHT)
        vertical = Qt.AlignmentFlag.AlignVCenter

        painter.setPen(QColor(235, 235, 240))
        name_rect = QRectF(row.left(), row.top(), 72, row.height())
        painter.drawText(name_rect, vertical | Qt.AlignmentFlag.AlignLeft, snapshot.display_name)

        if snapshot.status is not ProviderStatus.OK or not snapshot.windows:
            painter.setPen(QColor(150, 150, 160))
            text = self._status_text(snapshot)
            painter.drawText(row, vertical | Qt.AlignmentFlag.AlignRight, text)
            return

        used = snapshot.windows[0].used_pct
        shown = (100.0 - used) if self._settings.show_remaining else used

        bar = QRectF(
            right - 36 - self.BAR_WIDTH,
            row.center().y() - self.BAR_HEIGHT / 2,
            self.BAR_WIDTH,
            self.BAR_HEIGHT,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 34))
        painter.drawRoundedRect(bar, 3, 3)
        fill = bar.width() * max(0.0, min(1.0, shown / 100.0))
        if fill > 0:
            painter.setBrush(self._bar_color(used))
            painter.drawRoundedRect(QRectF(bar.left(), bar.top(), fill, bar.height()), 3, 3)

        painter.setPen(QColor(235, 235, 240))
        pct_rect = QRectF(right - 36, row.top(), 36, row.height())
        painter.drawText(pct_rect, vertical | Qt.AlignmentFlag.AlignRight, f"{shown:.0f}%")

    @staticmethod
    def _status_text(snapshot: UsageSnapshot) -> str:
        if snapshot.status is ProviderStatus.LOADING:
            return "..."
        if snapshot.status is ProviderStatus.NO_CREDENTIALS:
            return "sign in"
        if snapshot.status is ProviderStatus.EXPIRED:
            return "expired"
        return "error"

    @staticmethod
    def _bar_color(used_pct: float) -> QColor:
        if used_pct >= 85:
            return QColor(232, 92, 84)
        if used_pct >= 60:
            return QColor(232, 176, 74)
        return QColor(94, 197, 132)

    def enterEvent(self, event) -> None:
        self._fade_timer.stop()
        self._animate_opacity(self._settings.hover_opacity)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._dragging:
            self._fade_timer.start(self._settings.fade_delay_ms)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._fade_timer.stop()
            self._animate_opacity(self._settings.hover_opacity)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._settings.position = (self.x(), self.y())
            self._settings.save()
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self._fade_timer.start(self._settings.fade_delay_ms)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        build_context_menu(self).exec(event.globalPos())

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

    def _handle_screen_change(self) -> None:
        self.setFixedSize(self.sizeHint())
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
        if not self._dragging:
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
