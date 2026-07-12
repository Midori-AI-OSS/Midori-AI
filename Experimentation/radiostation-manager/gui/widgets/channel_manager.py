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
)

from gui.widgets.components import make_header, confirm


class ChannelManager(QWidget):
    back = Signal()
    channels_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._music_root = Path(".")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header, _ = make_header("Manage Channels", self.back.emit)
        layout.addLayout(header)

        lists_layout = QHBoxLayout()

        unblocked_widget = QVBoxLayout()
        unblocked_widget.addWidget(QLabel("Active Channels"))
        self._unblocked_list = QListWidget()
        self._unblocked_list.setAlternatingRowColors(True)
        self._unblocked_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        unblocked_widget.addWidget(self._unblocked_list)

        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        block_btn = QPushButton("Block →")
        block_btn.setObjectName("dangerButton")
        block_btn.clicked.connect(self._block_selected)
        btn_layout.addWidget(block_btn)
        btn_layout.addSpacing(8)
        unblock_btn = QPushButton("← Unblock")
        unblock_btn.setObjectName("successButton")
        unblock_btn.clicked.connect(self._unblock_selected)
        btn_layout.addWidget(unblock_btn)
        btn_layout.addStretch()

        blocked_widget = QVBoxLayout()
        blocked_widget.addWidget(QLabel("Blocked Channels"))
        self._blocked_list = QListWidget()
        self._blocked_list.setAlternatingRowColors(True)
        self._blocked_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        blocked_widget.addWidget(self._blocked_list)

        lists_layout.addLayout(unblocked_widget)
        lists_layout.addLayout(btn_layout)
        lists_layout.addLayout(blocked_widget)
        layout.addLayout(lists_layout)

    def load(self, music_root: Path, channels: list[str], blocked: list[str]):
        self._music_root = music_root
        self._unblocked_list.clear()
        self._blocked_list.clear()
        for ch in channels:
            if ch in blocked:
                self._blocked_list.addItem(ch)
            else:
                self._unblocked_list.addItem(ch)

    def _block_selected(self):
        from gui.core.metadata import block_channel

        selected = self._unblocked_list.selectedItems()
        if not selected:
            return
        names = [it.text() for it in selected]
        if not confirm(
            self,
            "Block Channels",
            "Block the following channel(s)?\n\n" + "\n".join(names),
        ):
            return
        for item in selected:
            block_channel(self._music_root, item.text())
        self.channels_changed.emit()

    def _unblock_selected(self):
        from gui.core.metadata import unblock_channel

        selected = self._blocked_list.selectedItems()
        if not selected:
            return
        names = [it.text() for it in selected]
        if not confirm(
            self,
            "Unblock Channels",
            "Unblock the following channel(s)?\n\n" + "\n".join(names),
        ):
            return
        for item in selected:
            unblock_channel(self._music_root, item.text())
        self.channels_changed.emit()
