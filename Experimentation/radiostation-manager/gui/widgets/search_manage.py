from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QGroupBox,
    QSplitter,
    QMessageBox,
)

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.metadata import scan_library, read_song, trash_file


class SearchManageFlow(QWidget):
    song_selected = Signal(Song)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._results: list[Song] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Search & Manage Songs")
        title.setObjectName("sectionLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("Back to Menu")
        back_btn.clicked.connect(self.back.emit)
        header.addWidget(back_btn)
        layout.addLayout(header)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "Enter keyword (case-insensitive, searches all fields)..."
        )
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input)
        search_btn = QPushButton("\U0001f50d Search")
        search_btn.setObjectName("accentButton")
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self._status_label = QLabel("Enter a keyword to search the library.")
        self._status_label.setObjectName("dimLabel")
        layout.addWidget(self._status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._show_detail)
        self._list.itemDoubleClicked.connect(self._edit_current)
        splitter.addWidget(self._list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        detail_group = QGroupBox("Song Details")
        detail_layout = QVBoxLayout(detail_group)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setPlaceholderText("Select a song to see details...")
        detail_layout.addWidget(self._detail_text)
        right_layout.addWidget(detail_group)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        edit_btn = QPushButton("Update Comment")
        edit_btn.clicked.connect(self._edit_current)
        action_row.addWidget(edit_btn)
        trash_btn = QPushButton("Trash")
        trash_btn.setObjectName("dangerButton")
        trash_btn.clicked.connect(self._trash_current)
        action_row.addWidget(trash_btn)
        action_row.addStretch()
        right_layout.addLayout(action_row)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([380, 360])
        layout.addWidget(splitter)

    def _do_search(self):
        keyword = self._search_input.text().strip().lower()
        if not keyword:
            return

        all_songs = scan_library(self._config.music_root, exclude_blocked=True)
        self._results = []
        tokens = keyword.split()
        for p in all_songs:
            song = read_song(p)
            searchable = (
                f"{song.title} {song.comment} {song.filename} "
                f"{song.music_theme} {song.why_made} {song.backstory} "
                f"{song.radio_reason} {song.listener_takeaway} {song.vibe_summary}"
            ).lower()
            if all(t in searchable for t in tokens):
                self._results.append(song)

        self._list.clear()
        for s in self._results:
            stars = ""
            if s.comment:
                stars = "  "
            self._list.addItem(f"{stars}{s.relative_path}  \u2014  {s.title}")
        self._status_label.setText(
            f'Found {len(self._results)} match{"es" if len(self._results) != 1 else ""} for "{keyword}"'
        )
        self._detail_text.clear()

    def _current_song(self) -> Song | None:
        item = self._list.currentItem()
        if item is None:
            return None
        idx = self._list.row(item)
        if 0 <= idx < len(self._results):
            return self._results[idx]
        return None

    def _show_detail(self, item: QListWidgetItem):
        idx = self._list.row(item)
        if 0 <= idx < len(self._results):
            s = self._results[idx]
            detail = f"\U0001f4c4 {s.relative_path}\n\n"
            detail += f"Title: {s.title}\n"
            detail += f"Comment: {s.comment or '(empty)'}\n\n"
            detail += f"Theme: {s.music_theme or 'none'}\n"
            detail += f"Why Made: {s.why_made or 'none'}\n"
            detail += f"Backstory: {s.backstory or 'none'}\n"
            detail += f"Radio Reason: {s.radio_reason or 'none'}\n"
            detail += f"Takeaway: {s.listener_takeaway or 'none'}\n"
            detail += f"Vibes: {s.vibe_summary or 'none'}"
            self._detail_text.setPlainText(detail)

    def _edit_current(self, item: QListWidgetItem | None = None):
        song = self._current_song()
        if song:
            self.song_selected.emit(song)

    def _trash_current(self):
        song = self._current_song()
        if song is None:
            return
        reply = QMessageBox.question(
            self,
            "Trash Song",
            f"Move this song to trash?\n\n{song.relative_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            trash_file(song.path)
            self._do_search()
