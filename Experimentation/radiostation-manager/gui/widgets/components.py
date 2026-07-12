from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QTimer,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def make_header(title: str, on_back_callable) -> tuple[QHBoxLayout, QHBoxLayout]:
    """Create a unified header with back button, centered title, and actions area.

    Returns (layout, actions_layout) where actions_layout can receive extra widgets.
    """
    layout = QHBoxLayout()
    layout.setSpacing(10)

    back_btn = QPushButton("\u2190 Back")
    back_btn.clicked.connect(on_back_callable)
    layout.addWidget(back_btn)

    layout.addStretch()

    title_label = QLabel(title)
    title_label.setObjectName("sectionLabel")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)

    layout.addStretch()

    actions = QWidget()
    actions_layout = QHBoxLayout(actions)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(8)
    layout.addWidget(actions)

    return layout, actions_layout


class StarRating(QWidget):
    """Five star buttons with rating 0-5. Emits rating_changed(int)."""

    rating_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rating = 0
        self._stars: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for i in range(5):
            btn = QPushButton("\u2605")
            btn.setFixedSize(30, 30)
            btn.setCheckable(True)
            btn.setObjectName("starButton")
            btn.clicked.connect(lambda checked, idx=i: self._set_rating(idx + 1))
            layout.addWidget(btn)
            self._stars.append(btn)

    def _set_rating(self, value: int):
        self._rating = value
        for i, btn in enumerate(self._stars):
            btn.setChecked(i < value)
        self.rating_changed.emit(value)

    @property
    def rating(self) -> int:
        return self._rating

    def clear(self):
        self._rating = 0
        for btn in self._stars:
            btn.setChecked(False)


class ToastWidget(QFrame):
    """Slide-in notification from top-right corner. Auto-dismisses after 3 seconds."""

    _active_count = 0
    _base_y = 12

    def __init__(self, parent: QWidget, text: str, level: str = "info"):
        super().__init__(parent)
        self.setObjectName("toastWidget")
        self.setFixedSize(340, 56)

        colors = {"success": "#4ecca3", "error": "#e94560", "info": "#00d4ff"}
        color = colors.get(level, "#00d4ff")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("dimLabel")
        layout.addWidget(label)

        self.setStyleSheet(
            f"QFrame#toastWidget {{"
            f"background-color: #1e1e3a; "
            f"border: 1px solid {color}; "
            f"border-left: 4px solid {color}; "
            f"border-radius: 8px; "
            f"}}"
        )

        ToastWidget._active_count += 1
        y = ToastWidget._base_y + (ToastWidget._active_count - 1) * 64

        pw = parent.width()
        target_x = pw - 352

        self.move(pw + 20, y)
        self.show()
        self.raise_()

        self._anim_in = QPropertyAnimation(self, b"geometry")
        self._anim_in.setDuration(300)
        self._anim_in.setStartValue(QRect(pw + 20, y, 340, 56))
        self._anim_in.setEndValue(QRect(target_x, y, 340, 56))
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._slide_out)
        self._timer.start(3000)

        self._anim_in.start()

    def _slide_out(self):
        geo = self.geometry()
        self._anim_out = QPropertyAnimation(self, b"geometry")
        self._anim_out.setDuration(300)
        self._anim_out.setStartValue(geo)
        self._anim_out.setEndValue(QRect(geo.x() + 360, geo.y(), 340, 56))
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_out.finished.connect(self._cleanup)
        self._anim_out.start()

    def _cleanup(self):
        ToastWidget._active_count = max(0, ToastWidget._active_count - 1)
        self.deleteLater()


class EmptyState(QWidget):
    """Centered placeholder with icon, title, and subtitle."""

    def __init__(self, icon: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setObjectName("emptyStateIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = icon_label.font()
        font.setPixelSize(40)
        icon_label.setFont(font)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        sub_label = QLabel(subtitle)
        sub_label.setObjectName("dimLabel")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)

        layout.addStretch()
        layout.insertStretch(0)


def confirm(parent: QWidget, title: str, message: str) -> bool:
    """Consistent confirmation dialog wrapping QMessageBox.question."""
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
