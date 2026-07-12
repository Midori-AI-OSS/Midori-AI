from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QStackedWidget,
)

from gui.widgets.components import make_header, EmptyState


class LibraryBrowser(QWidget):
    song_selected = Signal(Path)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._music_root = Path(".")
        self._tree: QTreeWidget = None  # type: ignore[assignment]
        self._status_label: QLabel = None  # type: ignore[assignment]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, actions = make_header("Update Comments", self.back.emit)

        self._status_label = QLabel()
        self._status_label.setObjectName("dimLabel")
        actions.addWidget(self._status_label)

        layout.addLayout(header)

        self._content_stack = QStackedWidget()
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Song", "Comment", "Vibes"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

        hdr = self._tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._empty = EmptyState(
            "\U0001f4da",
            "Your Library is Empty",
            "Import songs or check your music root directory.",
        )
        self._content_stack.addWidget(self._tree)
        self._content_stack.addWidget(self._empty)
        layout.addWidget(self._content_stack)

        btn_row = QHBoxLayout()
        edit_btn = QPushButton("Edit Selected")
        edit_btn.setObjectName("accentButton")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def load(self, music_root: Path, songs: list[dict]):
        self._music_root = music_root
        self._tree.setUpdatesEnabled(False)
        self._tree.clear()

        channels: dict[str, QTreeWidgetItem] = {}
        channel_counts: dict[str, int] = {}
        for s in songs:
            ch = s.get("channel", "Unknown")
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        for s in songs:
            channel = s.get("channel", "Unknown")
            if channel not in channels:
                ch_item = QTreeWidgetItem(
                    [f"{channel}  ({channel_counts[channel]})", "", ""]
                )
                ch_item.setFlags(ch_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                font = ch_item.font(0)
                font.setBold(True)
                ch_item.setFont(0, font)
                ch_item.setForeground(0, Qt.GlobalColor.cyan)
                self._tree.addTopLevelItem(ch_item)
                channels[channel] = ch_item

            item = QTreeWidgetItem(
                [
                    s.get("title", s.get("filename", "")),
                    s.get("comment", "")[:100],
                    s.get("vibe_summary", "")[:60],
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, str(s["path"]))
            channels[channel].addChild(item)

        self._tree.expandAll()
        self._tree.setUpdatesEnabled(True)
        total = len(songs)
        self._status_label.setText(f"{total} song{'s' if total != 1 else ''}")
        if songs:
            self._content_stack.setCurrentWidget(self._tree)
        else:
            self._content_stack.setCurrentWidget(self._empty)

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if path_str:
            self.song_selected.emit(Path(path_str))

    def _edit_selected(self):
        items = self._tree.selectedItems()
        for item in items:
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if path_str:
                self.song_selected.emit(Path(path_str))
                return
