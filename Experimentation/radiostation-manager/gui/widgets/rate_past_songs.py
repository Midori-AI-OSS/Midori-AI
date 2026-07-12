from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QLineEdit,
    QGroupBox,
    QSplitter,
)

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.metadata import scan_library, read_song
from gui.core.prompts import FeedbackEntry, FeedbackQueue


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
            btn = QPushButton("★")
            btn.setFixedSize(28, 28)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; font-size: 18px; color: #555; }
                QPushButton:checked { color: #f0a500; }
                QPushButton:hover { color: #f0a500; }
            """)
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


class RatePastSongs(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._songs: list[Song] = []
        self._current: Song | None = None
        self._detail_text: QTextEdit = None  # type: ignore[assignment]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("Rate Past Songs")
        title.setObjectName("sectionLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("Back to Menu")
        back_btn.clicked.connect(self.back.emit)
        header.addWidget(back_btn)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._song_list = QListWidget()
        self._song_list.itemClicked.connect(self._on_select)
        left_layout.addWidget(self._song_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_group = QGroupBox("Song Details")
        detail_layout = QVBoxLayout(detail_group)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        detail_layout.addWidget(self._detail_text)
        right_layout.addWidget(detail_group)

        rate_group = QGroupBox("Rate")
        rate_layout = QVBoxLayout(rate_group)
        star_row = QHBoxLayout()
        star_row.addWidget(QLabel("Rating:"))
        self._stars = StarRating()
        star_row.addWidget(self._stars)
        star_row.addStretch()
        rate_layout.addLayout(star_row)
        self._note_input = QLineEdit()
        self._note_input.setPlaceholderText("Optional note...")
        rate_layout.addWidget(self._note_input)
        submit_btn = QPushButton("Submit Rating")
        submit_btn.setObjectName("accentButton")
        submit_btn.clicked.connect(self._submit)
        rate_layout.addWidget(submit_btn)
        right_layout.addWidget(rate_group)

        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

    def refresh(self):
        all_songs = scan_library(self._config.music_root, exclude_blocked=True)
        self._songs = [read_song(p) for p in all_songs]
        self._song_list.clear()
        for s in self._songs:
            rating_marker = "    " if not s.comment else " ★  "
            self._song_list.addItem(f"{rating_marker}{s.relative_path}  —  {s.title}")

    def _on_select(self, item: QListWidgetItem):
        idx = self._song_list.row(item)
        if 0 <= idx < len(self._songs):
            self._current = self._songs[idx]
            s = self._current
            detail = f"File: {s.relative_path}\n\n"
            detail += f"Title: {s.title}\n\n"
            detail += f"Comment: {s.comment or '(empty)'}\n\n"
            detail += f"Theme: {s.music_theme or 'none'}\n"
            detail += f"Why Made: {s.why_made or 'none'}\n"
            detail += f"Backstory: {s.backstory or 'none'}\n"
            detail += f"Radio Reason: {s.radio_reason or 'none'}\n"
            detail += f"Takeaway: {s.listener_takeaway or 'none'}\n"
            detail += f"Vibes: {s.vibe_summary or 'none'}"
            self._detail_text.setPlainText(detail)
            self._stars.clear()
            self._note_input.clear()

    def _submit(self):
        if self._current is None or self._stars.rating == 0:
            return
        entry = FeedbackEntry(
            rating=self._stars.rating,
            output=self._current.comment,
            prompt_template="song_statement",
            song_title=self._current.title,
            song_context=f"channel: {self._current.channel}, theme: {self._current.music_theme}",
            note=self._note_input.text().strip(),
        )
        queue = FeedbackQueue(self._config.feedback_queue_path)
        queue.append(entry)
        self._stars.clear()
        self._note_input.clear()
        self._detail_text.setPlainText(
            "Rating submitted! Select another song or go back."
        )
