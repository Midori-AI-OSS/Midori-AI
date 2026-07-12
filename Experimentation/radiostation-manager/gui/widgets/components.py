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
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def make_header(title: str, on_back_callable) -> tuple[QVBoxLayout, QHBoxLayout]:
    """Create a unified two-row header:
    Row 1: ← Back | spacer | [actions]
    Row 2: TITLE centered large
    Returns (layout, actions_layout for caller to add extra buttons)
    """
    layout = QVBoxLayout()
    layout.setSpacing(0)

    top_row = QHBoxLayout()
    top_row.setSpacing(6)

    back_btn = QPushButton("\u2190 Back")
    back_btn.clicked.connect(on_back_callable)
    top_row.addWidget(back_btn)

    top_row.addStretch()

    actions = QWidget()
    actions_layout = QHBoxLayout(actions)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(8)
    top_row.addWidget(actions)

    layout.addLayout(top_row)

    title_label = QLabel(title)
    title_label.setObjectName("sectionLabel")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)

    layout.addSpacing(8)

    return layout, actions_layout


class StarRating(QWidget):
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


class LoadingPage(QWidget):
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadingPage")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        self._spinner = QLabel("\U0001f3b5")
        self._spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._spinner.font()
        font.setPixelSize(48)
        self._spinner.setFont(font)
        layout.addWidget(self._spinner)

        self._message = QLabel("Loading...")
        self._message.setObjectName("headerLabel")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._message)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedWidth(320)
        layout.addWidget(self._progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self._detail = QLabel()
        self._detail.setObjectName("dimLabel")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail.setWordWrap(True)
        self._detail.setMaximumWidth(420)
        layout.addWidget(self._detail)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("exitButton")
        cancel_btn.clicked.connect(self.cancelled.emit)
        layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_message(self, text: str):
        self._message.setText(text)

    def set_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)

    def set_detail(self, text: str):
        self._detail.setText(text)


def confirm(parent: QWidget, title: str, message: str) -> bool:
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
