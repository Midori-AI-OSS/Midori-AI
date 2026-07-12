from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.core.config import get_config
from gui.widgets.components import ToastWidget
from gui.widgets.main_menu import MainMenu
from gui.widgets.comment_editor import CommentEditor
from gui.widgets.import_flow import ImportFlow
from gui.widgets.library_browser import LibraryBrowser
from gui.widgets.stale_comments import StaleCommentsFlow
from gui.widgets.search_manage import SearchManageFlow
from gui.widgets.rate_past_songs import RatePastSongs
from gui.widgets.cache_vibes import CacheVibesFlow
from gui.widgets.channel_manager import ChannelManager
from gui.widgets.prompt_manager import PromptManager
from gui.core.metadata import (
    scan_library,
    read_song,
    get_channel_dirs,
    is_channel_blocked,
)
from gui.core.song import Song

SIDEBAR_ITEMS = [
    ("\U0001f4e5", "import"),
    ("\U0001f4dd", "update"),
    ("\U0001f504", "stale"),
    ("\U0001f50d", "search"),
    ("\u2b50", "rate"),
    ("\U0001f3b5", "vibes"),
    ("\U0001f512", "channels"),
    ("\U0001f916", "prompts"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luna Music Metadata Studio")
        self.setMinimumSize(1024, 576)
        self.resize(1280, 720)

        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

        self._config = get_config()
        self._stack = QStackedWidget()

        self._widgets: dict[str, QWidget] = {}
        self._sidebar_btns: dict[str, QPushButton] = {}

        self._sidebar = self._create_sidebar()

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(self._stack)
        self.setCentralWidget(body)

        self._main_menu = MainMenu()
        self._main_menu.navigate.connect(self._on_navigate)
        self._widgets["menu"] = self._main_menu

        self._import_flow = ImportFlow()
        self._import_flow.back.connect(lambda: self._go_to("menu"))
        self._import_flow.song_ready_for_edit.connect(self._open_comment_editor)
        self._widgets["import"] = self._import_flow

        self._library_browser = LibraryBrowser()
        self._library_browser.back.connect(lambda: self._go_to("menu"))
        self._library_browser.song_selected.connect(self._open_comment_editor_from_path)
        self._widgets["update"] = self._library_browser

        self._stale_flow = StaleCommentsFlow()
        self._stale_flow.back.connect(lambda: self._go_to("menu"))
        self._stale_flow.song_selected.connect(self._open_comment_editor)
        self._widgets["stale"] = self._stale_flow

        self._search_flow = SearchManageFlow()
        self._search_flow.back.connect(lambda: self._go_to("menu"))
        self._search_flow.song_selected.connect(self._open_comment_editor)
        self._widgets["search"] = self._search_flow

        self._rate_flow = RatePastSongs()
        self._rate_flow.back.connect(lambda: self._go_to("menu"))
        self._widgets["rate"] = self._rate_flow

        self._vibes_flow = CacheVibesFlow()
        self._vibes_flow.back.connect(lambda: self._go_to("menu"))
        self._widgets["vibes"] = self._vibes_flow

        self._channel_mgr = ChannelManager()
        self._channel_mgr.back.connect(lambda: self._go_to("menu"))
        self._channel_mgr.channels_changed.connect(self._refresh_channel_mgr)
        self._widgets["channels"] = self._channel_mgr

        self._prompt_mgr = PromptManager()
        self._prompt_mgr.back.connect(lambda: self._go_to("menu"))
        self._widgets["prompts"] = self._prompt_mgr

        self._comment_editor = CommentEditor()
        self._comment_editor.finished.connect(self._on_comment_saved)
        self._comment_editor.cancelled.connect(self._on_editor_cancel)
        self._widgets["editor"] = self._comment_editor

        for w in self._widgets.values():
            self._stack.addWidget(w)

        self._stack.setCurrentWidget(self._main_menu)
        self._sidebar.hide()

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(48)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(2)

        for icon, key in SIDEBAR_ITEMS:
            btn = QPushButton(icon)
            btn.setObjectName("sidebarButton")
            btn.setFixedSize(40, 40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._on_navigate(k))
            layout.addWidget(btn)
            self._sidebar_btns[key] = btn

        layout.addStretch()
        return sidebar

    def _set_sidebar_active(self, key: str | None):
        for k, btn in self._sidebar_btns.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_navigate(self, key: str):
        if key == "exit":
            self.close()
            return

        if key == "menu":
            self._go_to("menu")
            return

        self._sidebar.show()
        self._set_sidebar_active(key)

        if key == "import":
            self._stack.setCurrentWidget(self._import_flow)
            self._import_flow._refresh()
        elif key == "update":
            self._refresh_library_browser()
            self._stack.setCurrentWidget(self._library_browser)
        elif key == "stale":
            self._stale_flow.refresh()
            self._stack.setCurrentWidget(self._stale_flow)
        elif key == "search":
            self._stack.setCurrentWidget(self._search_flow)
        elif key == "rate":
            self._rate_flow.refresh()
            self._stack.setCurrentWidget(self._rate_flow)
        elif key == "vibes":
            self._stack.setCurrentWidget(self._vibes_flow)
        elif key == "channels":
            self._refresh_channel_mgr()
            self._stack.setCurrentWidget(self._channel_mgr)
        elif key == "prompts":
            self._stack.setCurrentWidget(self._prompt_mgr)

    def _go_to(self, key: str):
        self._sidebar.hide()
        self._set_sidebar_active(None)
        self._stack.setCurrentWidget(self._widgets[key])

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._go_to("menu")
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Q:
                self.close()
                return
            k = event.key()
            key_map = {
                Qt.Key.Key_1: "import",
                Qt.Key.Key_2: "update",
                Qt.Key.Key_3: "stale",
                Qt.Key.Key_4: "search",
                Qt.Key.Key_5: "rate",
                Qt.Key.Key_6: "vibes",
                Qt.Key.Key_7: "channels",
                Qt.Key.Key_8: "prompts",
            }
            target = key_map.get(k)  # type: ignore[arg-type]
            if target:
                self._on_navigate(target)
                return
        super().keyPressEvent(event)

    def show_toast(self, text: str, level: str = "info"):
        """Show a transient toast notification. Levels: success, error, info."""
        central = self.centralWidget()
        if central:
            ToastWidget(central, text, level)

    def _open_comment_editor(self, song: Song):
        self._sidebar.show()
        self._set_sidebar_active(None)
        self._comment_editor.load_song(song)
        self._stack.setCurrentWidget(self._comment_editor)

    def _open_comment_editor_from_path(self, path: Path):
        song = read_song(path)
        self._open_comment_editor(song)

    def _on_comment_saved(self, song: Song):
        self._stack.setCurrentWidget(self._main_menu)

    def _on_editor_cancel(self):
        self._stack.setCurrentWidget(self._main_menu)

    def _refresh_library_browser(self):
        songs = scan_library(self._config.music_root, exclude_blocked=True)
        data = []
        for p in songs:
            s = read_song(p)
            data.append(
                {
                    "path": p,
                    "channel": s.channel,
                    "title": s.title,
                    "comment": s.comment,
                    "vibe_summary": s.vibe_summary,
                    "filename": p.name,
                }
            )
        self._library_browser.load(self._config.music_root, data)

    def _refresh_channel_mgr(self):
        channels = get_channel_dirs(self._config.music_root)
        blocked = [
            c for c in channels if is_channel_blocked(self._config.music_root, c)
        ]
        self._channel_mgr.load(self._config.music_root, channels, blocked)
