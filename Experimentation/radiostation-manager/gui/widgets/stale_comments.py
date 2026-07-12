from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
)

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.metadata import scan_library, read_song, is_outdated_comment
from gui.widgets.components import make_header, EmptyState


class StaleCommentsFlow(QWidget):
    song_selected = Signal(Song)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._stale_songs: list[dict] = []
        self._all_total = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Update Stale Comments", self.back.emit)
        layout.addLayout(header)

        self._status_label = QLabel()
        self._status_label.setObjectName("dimLabel")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._content_stack = QStackedWidget()
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._empty = EmptyState(
            "\u2705",
            "All Comments Up to Date",
            "No stale markers found in your library.",
        )
        self._content_stack.addWidget(self._list)
        self._content_stack.addWidget(self._empty)
        layout.addWidget(self._content_stack)

        btn_row = QHBoxLayout()
        fix_btn = QPushButton("\u270f\ufe0f Fix Selected")
        fix_btn.setObjectName("accentButton")
        fix_btn.clicked.connect(self._fix_selected)
        btn_row.addWidget(fix_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def set_data(self, songs: list[dict]):
        """Called from main thread with pre-loaded data from worker thread."""
        from gui.core.metadata import is_outdated_comment

        self._stale_songs = [
            s for s in songs if is_outdated_comment(s.get("comment", ""))
        ]
        self._all_total = len(songs)
        self._list.clear()
        for s in self._stale_songs:
            rel = (
                s.get("channel", "") + "/" + s.get("filename", "")
                if s.get("channel")
                else s.get("filename", "")
            )
            comment = s.get("comment", "")[:80]
            self._list.addItem(f"\U0001f504 {rel}  \u2014  {comment}")

        if self._stale_songs:
            n = len(self._stale_songs)
            self._status_label.setText(
                f"\U0001f4cb Found {n} song{'s' if n != 1 else ''} "
                f"with outdated markers out of {self._all_total} total"
            )
            self._content_stack.setCurrentWidget(self._list)
        else:
            self._status_label.setText(
                f"\u2705 All {self._all_total} song comments are up to date."
            )
            self._content_stack.setCurrentWidget(self._empty)

    def _fix_selected(self):
        item = self._list.currentItem()
        if item:
            self._on_double_click(item)

    def _on_double_click(self, item: QListWidgetItem):
        idx = self._list.row(item)
        if 0 <= idx < len(self._stale_songs):
            from gui.core.metadata import read_song as _read

            s = self._stale_songs[idx]
            song = _read(s.get("path", Path(".")))  # type: ignore[arg-type]
            self.song_selected.emit(song)
