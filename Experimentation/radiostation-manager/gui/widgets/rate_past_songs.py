from __future__ import annotations


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
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStyle,
)

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.prompts import FeedbackEntry, FeedbackQueue
from gui.widgets.components import make_header, StarRating, EmptyState


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
        layout.setSpacing(10)

        header, _ = make_header("Rate Past Songs", self.back.emit)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._content_stack = QStackedWidget()
        self._song_list = QListWidget()
        self._song_list.setAlternatingRowColors(True)
        self._song_list.itemClicked.connect(self._on_select)
        self._empty = EmptyState(
            QStyle.StandardPixmap.SP_MessageBoxQuestion,
            "No Songs to Rate",
            "Your library is empty. Import some songs first.",
        )
        self._content_stack.addWidget(self._song_list)
        self._content_stack.addWidget(self._empty)
        left_layout.addWidget(self._content_stack)
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
        """Legacy: triggers loading via worker. Called internally."""
        pass

    def set_data(self, songs_data: list[dict]):
        self._songs = []
        for sd in songs_data:
            self._songs.append(
                Song(
                    path=sd["path"],
                    title=sd["title"],
                    comment=sd["comment"],
                    why_made=sd.get("why_made", ""),
                    backstory=sd.get("backstory", ""),
                    radio_reason=sd.get("radio_reason", ""),
                    music_theme=sd.get("music_theme", ""),
                    listener_takeaway=sd.get("listener_takeaway", ""),
                    vibe_analysis=sd.get("vibe_analysis", ""),
                    vibe_summary=sd.get("vibe_summary", ""),
                    vibe_cached_at_epoch=sd.get("vibe_cached_at_epoch", ""),
                    vibe_cache_schema=sd.get("vibe_cache_schema", ""),
                )
            )
        self._song_list.clear()
        for s in self._songs:
            rating_marker = "    " if not s.comment else " ★  "
            self._song_list.addItem(f"{rating_marker}{s.relative_path}  —  {s.title}")
        if self._songs:
            self._content_stack.setCurrentWidget(self._song_list)
        else:
            self._content_stack.setCurrentWidget(self._empty)

    def _on_select(self, item: QListWidgetItem):
        idx = self._song_list.row(item)
        if 0 <= idx < len(self._songs):
            self._current = self._songs[idx]
            s = self._current
            detail = f"File: {s.relative_path}\n\n"
            detail += f"Title: {s.title}\n\n"
            detail += f"Comment: {s.comment or '(empty)'}"
            self._detail_text.setPlainText(detail)
            self._stars.clear()
            self._note_input.clear()

    def _submit(self):
        if self._current is None:
            QMessageBox.information(
                self, "No Song Selected", "Select a song from the list first."
            )
            return
        if self._stars.rating == 0:
            QMessageBox.information(
                self, "No Rating", "Click stars to set a rating first."
            )
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
