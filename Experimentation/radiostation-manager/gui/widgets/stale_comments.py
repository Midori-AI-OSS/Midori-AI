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
)

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.metadata import scan_library, read_song, is_outdated_comment


class StaleCommentsFlow(QWidget):
    song_selected = Signal(Song)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._stale_songs: list[Path] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Update Stale Comments")
        title.setObjectName("sectionLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("Back to Menu")
        back_btn.clicked.connect(self.back.emit)
        header.addWidget(back_btn)
        layout.addLayout(header)

        self._status_label = QLabel()
        self._status_label.setObjectName("dimLabel")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        fix_btn = QPushButton("\u270f\ufe0f Fix Selected")
        fix_btn.setObjectName("accentButton")
        fix_btn.clicked.connect(self._fix_selected)
        btn_row.addWidget(fix_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self):
        all_songs = scan_library(self._config.music_root, exclude_blocked=True)
        stale = [p for p in all_songs if is_outdated_comment(read_song(p).comment)]

        self._stale_songs = stale
        self._list.clear()
        for p in stale:
            song = read_song(p)
            self._list.addItem(
                f"\U0001f504 {song.relative_path}  \u2014  {song.comment[:80]}"
            )

        if stale:
            self._status_label.setText(
                f"\U0001f4cb Found {len(stale)} song{'s' if len(stale) != 1 else ''} "
                f"with outdated markers out of {len(all_songs)} total"
            )
        else:
            self._status_label.setText(
                f"\u2705 All {len(all_songs)} song comments are up to date \u2014 no stale markers found."
            )

    def _fix_selected(self):
        item = self._list.currentItem()
        if item:
            self._on_double_click(item)

    def _on_double_click(self, item: QListWidgetItem):
        idx = self._list.row(item)
        if 0 <= idx < len(self._stale_songs):
            self.song_selected.emit(read_song(self._stale_songs[idx]))
