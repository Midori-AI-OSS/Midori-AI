from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QComboBox,
    QMessageBox,
    QStackedWidget,
)

from gui.widgets.components import make_header, EmptyState

from gui.core.config import get_config
from gui.core.song import Song
from gui.core.metadata import (
    scan_downloads,
    scan_library,
    get_channel_dirs,
    recommend_channel,
    read_song,
)


class ImportFlow(QWidget):
    song_ready_for_edit = Signal(Song)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = get_config()
        self._downloads: list[Path] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Import Song(s)", self.back.emit)
        layout.addLayout(header)

        self._count_label = QLabel()
        self._count_label.setObjectName("dimLabel")
        self._count_label.setWordWrap(True)
        layout.addWidget(self._count_label)

        self._content_stack = QStackedWidget()
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._empty = EmptyState(
            "\U0001f4e5",
            "No Songs to Import",
            "All downloads are already in your library.",
        )
        self._content_stack.addWidget(self._list)
        self._content_stack.addWidget(self._empty)
        layout.addWidget(self._content_stack)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.addWidget(QLabel("Target Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.setMinimumWidth(180)
        controls.addWidget(self._channel_combo)
        controls.addStretch()
        self._import_btn = QPushButton("\U0001f4e5 Import Selected")
        self._import_btn.setObjectName("accentButton")
        self._import_btn.clicked.connect(self._import_selected)
        self._import_btn.setEnabled(False)
        controls.addWidget(self._import_btn)
        layout.addLayout(controls)

        self._status_label = QLabel()
        self._status_label.setObjectName("dimLabel")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _refresh(self):
        all_downloads = (
            scan_downloads(self._config.downloads_dir)
            if self._config.downloads_dir.exists()
            else []
        )
        library = {p.name.lower() for p in scan_library(self._config.music_root)}
        self._downloads = [d for d in all_downloads if d.name.lower() not in library]

        self._list.clear()
        for d in self._downloads:
            self._list.addItem(d.name)

        channels = get_channel_dirs(self._config.music_root)
        self._channel_combo.clear()
        self._channel_combo.addItems(channels)

        self._count_label.setText(
            f"\U0001f4c1 {len(all_downloads)} MP3s in Downloads \u2192 "
            f"\U0001f4e5 {len(self._downloads)} not yet imported (newest first)"
        )
        self._import_btn.setEnabled(len(self._downloads) > 0)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        if self._downloads:
            self._content_stack.setCurrentWidget(self._list)
        else:
            self._content_stack.setCurrentWidget(self._empty)

    def _on_selection_changed(self):
        selected = self._list.selectedItems()
        if not selected or not self._downloads:
            return
        first = self._downloads[self._list.row(selected[0])]
        channels = get_channel_dirs(self._config.music_root)
        recommended = recommend_channel(first.name, channels)
        if recommended:
            idx = self._channel_combo.findText(recommended)
            if idx >= 0:
                self._channel_combo.setCurrentIndex(idx)

    def _import_selected(self):
        selected = self._list.selectedItems()
        if not selected:
            return
        channel = self._channel_combo.currentText()
        if not channel:
            QMessageBox.warning(self, "No Channel", "Select a target channel first.")
            return

        channel_dir = self._config.music_root / channel
        channel_dir.mkdir(parents=True, exist_ok=True)

        for item in selected:
            src = self._downloads[self._list.row(item)]
            dst = channel_dir / src.name
            count = 1
            while dst.exists():
                stem = src.stem
                dst = channel_dir / f"{stem} ({count}){src.suffix}"
                count += 1
            shutil.copy2(src, dst)
            song = read_song(dst)
            pwin = self.window()
            if hasattr(pwin, "show_toast"):
                pwin.show_toast(f"\u2705 Imported {dst.name}", "success")
            self.song_ready_for_edit.emit(song)

        self._refresh()
