from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGridLayout,
    QSizePolicy,
    QStyle,
)

ICON_MAP = {
    "import": QStyle.StandardPixmap.SP_ArrowDown,
    "update": QStyle.StandardPixmap.SP_FileIcon,
    "stale": QStyle.StandardPixmap.SP_BrowserReload,
    "search": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "rate": QStyle.StandardPixmap.SP_MessageBoxQuestion,
    "vibes": QStyle.StandardPixmap.SP_MediaPlay,
    "channels": QStyle.StandardPixmap.SP_DirIcon,
    "prompts": QStyle.StandardPixmap.SP_ComputerIcon,
}


class MenuCard(QPushButton):
    def __init__(self, key: str, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("menuButton")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        sp_icon = ICON_MAP.get(key)
        if sp_icon is not None:
            icon_label = QLabel()
            icon_label.setPixmap(
                icon_label.style()
                .standardIcon(sp_icon)
                .pixmap(QSize(32, 32))
            )
            icon_label.setObjectName("menuCardIcon")
            layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("menuCardTitle")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("dimLabel")
        layout.addWidget(desc_label)

        layout.addStretch()


class MainMenu(QWidget):
    navigate = Signal(str)

    ITEMS = [
        (
            "import",
            "Import Song(s)",
            "Copy new songs from Downloads into a channel and write metadata",
        ),
        (
            "update",
            "Update Comments",
            "Browse the library and edit song comments with LRM assistance",
        ),
        (
            "stale",
            "Update Stale Comments",
            "Review songs with outdated markers like Suno boilerplate",
        ),
        (
            "search",
            "Search & Manage",
            "Search by keyword and Play, Update, View, or Trash results",
        ),
        (
            "rate",
            "Rate Past Songs",
            "Browse the library, review existing comments, and rate them",
        ),
        (
            "vibes",
            "Cache All Vibes",
            "Run Essentia audio analysis on every song in parallel",
        ),
        (
            "channels",
            "Block/Unblock Channels",
            "Toggle which channel folders are visible in the library",
        ),
        (
            "prompts",
            "Manage Prompts",
            "Edit prompt templates, view feedback queue, and refine prompts",
        ),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 32)
        layout.setSpacing(0)

        header = QLabel("Luna's Music Metadata Studio")
        header.setObjectName("headerLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        sub = QLabel(
            "Manage your radio station\u2019s music collection with LRM-assisted metadata"
        )
        sub.setObjectName("subHeaderLabel")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(28)

        grid = QGridLayout()
        grid.setSpacing(14)
        cols = 4
        for i, (key, title, desc) in enumerate(self.ITEMS):
            card = MenuCard(key, title, desc)
            card.clicked.connect(lambda checked, k=key: self.navigate.emit(k))
            grid.addWidget(card, i // cols, i % cols)

        layout.addLayout(grid)
        layout.addStretch()

        bottom = QHBoxLayout()
        bottom.addStretch()
        exit_btn = QPushButton("Exit")
        exit_btn.setObjectName("exitButton")
        exit_btn.clicked.connect(lambda: self.navigate.emit("exit"))
        bottom.addWidget(exit_btn)
        bottom.addStretch()
        layout.addLayout(bottom)
