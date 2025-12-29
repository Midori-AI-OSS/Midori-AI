import math

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QWidget


class GlassCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def paintEvent(self, event) -> None:
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRect(rect)

        painter.fillPath(path, QColor(18, 20, 28, 165))
        painter.setPen(QColor(255, 255, 255, 25))
        painter.drawPath(path)


class ArcSpinner(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 44) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 6.0) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = self.rect().center()
        ring_r = min(self.width(), self.height()) * 0.36

        for i in range(12):
            t = (i / 12.0) * math.tau
            angle_deg = math.degrees(t) + self._angle
            alpha = int(22 + (i / 12.0) * 190)

            color = QColor(56, 189, 248, alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)

            x = center.x() + math.cos(math.radians(angle_deg)) * ring_r
            y = center.y() + math.sin(math.radians(angle_deg)) * ring_r
            r = 3.4
            painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))


class StatusGlyph(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 18) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._mode = "idle"
        self._color = QColor(148, 163, 184, 220)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)

    def set_mode(self, mode: str, color: QColor | None = None) -> None:
        self._mode = mode
        if color is not None:
            self._color = color
        if mode == "spinner":
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 7.0) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        center = rect.center()
        size = min(rect.width(), rect.height())
        ring_r = size * 0.36

        if self._mode == "spinner":
            for i in range(12):
                t = (i / 12.0) * math.tau
                angle_deg = math.degrees(t) + self._angle
                alpha = int(30 + (i / 12.0) * 200)
                color = QColor(self._color.red(), self._color.green(), self._color.blue(), alpha)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)

                x = center.x() + math.cos(math.radians(angle_deg)) * ring_r
                y = center.y() + math.sin(math.radians(angle_deg)) * ring_r
                r = max(2.0, size * 0.14)
                painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))
            return

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color.red(), self._color.green(), self._color.blue(), 45))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        pen = painter.pen()
        pen.setWidthF(max(1.6, size * 0.12))
        pen.setColor(QColor(self._color.red(), self._color.green(), self._color.blue(), 220))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        if self._mode == "check":
            path = QPainterPath()
            path.moveTo(rect.left() + size * 0.28, rect.top() + size * 0.55)
            path.lineTo(rect.left() + size * 0.44, rect.top() + size * 0.70)
            path.lineTo(rect.left() + size * 0.74, rect.top() + size * 0.34)
            painter.drawPath(path)
            return

        if self._mode == "x":
            painter.drawLine(
                int(rect.left() + size * 0.30),
                int(rect.top() + size * 0.30),
                int(rect.left() + size * 0.70),
                int(rect.top() + size * 0.70),
            )
            painter.drawLine(
                int(rect.left() + size * 0.70),
                int(rect.top() + size * 0.30),
                int(rect.left() + size * 0.30),
                int(rect.top() + size * 0.70),
            )
            return


class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        def fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(color)
            if bold:
                f.setFontWeight(700)
            return f

        slate = QColor(148, 163, 184, 235)
        cyan = QColor(56, 189, 248, 235)
        emerald = QColor(16, 185, 129, 235)
        rose = QColor(244, 63, 94, 235)
        amber = QColor(245, 158, 11, 235)

        self._rules: list[tuple[object, QTextCharFormat]] = [
            (r"^\[\d{2}:\d{2}:\d{2}\]", fmt(slate, False)),
            (r"\[host\]", fmt(cyan, True)),
            (r"\[preflight\]", fmt(emerald, True)),
            (r"\bpull complete\b", fmt(emerald, True)),
            (r"\bdocker pull\b", fmt(cyan, True)),
            (r"\b(exit|exited)\b", fmt(amber, True)),
            (r"\b(error|failed|fatal|exception)\b", fmt(rose, True)),
        ]

    def highlightBlock(self, text: str) -> None:
        import re

        for pattern, style in self._rules:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), style)
