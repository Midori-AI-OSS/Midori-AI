from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
)

from gui.core.config import get_config
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luna Music Metadata Studio")
        self.setMinimumSize(900, 680)

        self._config = get_config()
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._widgets: dict[str, QWidget] = {}

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

    def _on_navigate(self, key: str):
        if key == "exit":
            self.close()
            return
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
        self._stack.setCurrentWidget(self._widgets[key])

    def _open_comment_editor(self, song: Song):
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
