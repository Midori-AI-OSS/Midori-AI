from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from gui.core.config import get_config
from gui.core.library_worker import LibraryScanWorker, DownloadScanWorker
from gui.core.metadata import (
    read_song,
    get_channel_dirs,
    is_channel_blocked,
)
from gui.core.song import Song
from gui.widgets.components import ToastWidget, LoadingPage
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

SIDEBAR_ITEMS = [
    (QStyle.StandardPixmap.SP_ArrowDown, "import", "Import Songs"),
    (QStyle.StandardPixmap.SP_FileIcon, "update", "Update Comments"),
    (QStyle.StandardPixmap.SP_BrowserReload, "stale", "Stale Comments"),
    (QStyle.StandardPixmap.SP_FileDialogContentsView, "search", "Search & Manage"),
    (QStyle.StandardPixmap.SP_MessageBoxQuestion, "rate", "Rate Songs"),
    (QStyle.StandardPixmap.SP_MediaPlay, "vibes", "Cache Vibes"),
    (QStyle.StandardPixmap.SP_DirIcon, "channels", "Channels"),
    (QStyle.StandardPixmap.SP_ComputerIcon, "prompts", "Prompts"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luna's Music Metadata Studio")
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
        self._scan_worker: LibraryScanWorker | None = None
        self._download_worker: DownloadScanWorker | None = None
        self._previous_page: str = "menu"

        self._sidebar = self._create_sidebar()

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(self._stack)
        self.setCentralWidget(body)

        self._loading_page = LoadingPage()
        self._loading_page.cancelled.connect(self._on_loading_cancelled)
        self._widgets["_loading"] = self._loading_page
        self._stack.addWidget(self._loading_page)

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

        for sp_icon, key, tooltip in SIDEBAR_ITEMS:
            btn = QPushButton()
            btn.setIcon(self.style().standardIcon(sp_icon))
            btn.setIconSize(QSize(20, 20))
            btn.setToolTip(tooltip)
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

    def _show_loading(self, message: str):
        self._loading_page.set_message(message)
        self._loading_page.set_progress(0, 100)
        self._loading_page.set_detail("")
        self._stack.setCurrentWidget(self._loading_page)

    def _hide_loading(self):
        if self._stack.currentWidget() is self._loading_page:
            self._stack.setCurrentWidget(
                self._widgets.get(self._previous_page, self._main_menu)
            )

    def _cancel_scan(self):
        try:
            if self._scan_worker and self._scan_worker.isRunning():
                self._scan_worker.cancel()
                self._scan_worker.wait(2000)
        except RuntimeError:
            self._scan_worker = None
        try:
            if self._download_worker and self._download_worker.isRunning():
                self._download_worker.cancel()
                self._download_worker.wait(2000)
        except RuntimeError:
            self._download_worker = None
        self._hide_loading()

    def _on_loading_cancelled(self):
        self._cancel_scan()
        self._go_to("menu")

    def _on_navigate(self, key: str):
        if key == "exit":
            self.close()
            return

        if key == "menu":
            self._go_to("menu")
            return

        self._sidebar.show()
        self._set_sidebar_active(key)
        self._previous_page = key

        if key == "import":
            self._load_import_page()
        elif key == "update":
            self._load_library_page()
        elif key == "stale":
            self._load_stale_page()
        elif key == "search":
            self._stack.setCurrentWidget(self._search_flow)
        elif key == "rate":
            self._load_rate_page()
        elif key == "vibes":
            self._stack.setCurrentWidget(self._vibes_flow)
        elif key == "channels":
            self._refresh_channel_mgr()
            self._stack.setCurrentWidget(self._channel_mgr)
        elif key == "prompts":
            self._prompt_mgr._refresh_queue()
            self._stack.setCurrentWidget(self._prompt_mgr)

    def _go_to(self, key: str):
        self._cancel_scan()
        self._sidebar.hide()
        self._set_sidebar_active(None)
        self._previous_page = key
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
        central = self.centralWidget()
        if central:
            ToastWidget(central, text, level)

    def _start_scan(self, exclude_blocked: bool = True, message: str = "Loading..."):
        self._cancel_scan()
        self._show_loading(message)
        self._scan_worker = LibraryScanWorker(
            self._config.music_root, exclude_blocked=exclude_blocked
        )
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        return self._scan_worker

    def _on_scan_progress(self, current: int, total: int, status: str):
        self._loading_page.set_progress(current, total)
        self._loading_page.set_detail(status)

    def _load_library_page(self):
        self._stack.setCurrentWidget(self._library_browser)
        self._previous_page = "update"
        worker = self._start_scan(message="Loading your music library...")
        worker.songs_ready.connect(self._on_library_data)
        worker.error_occurred.connect(lambda e: self.show_toast(f"Error: {e}", "error"))
        worker.start()

    def _on_library_data(self, songs: list[dict]):
        self._hide_loading()
        self._library_browser.load(self._config.music_root, songs)
        self._stack.setCurrentWidget(self._library_browser)

    def _load_import_page(self):
        self._stack.setCurrentWidget(self._import_flow)
        self._previous_page = "import"
        self._show_loading("Checking Downloads folder...")
        self._download_worker = DownloadScanWorker(
            self._config.downloads_dir, self._config.music_root
        )
        self._download_worker.ready.connect(self._on_downloads_data)
        self._download_worker.error_occurred.connect(
            lambda e: self.show_toast(f"Error: {e}", "error")
        )
        self._download_worker.start()

    def _on_downloads_data(self, all_downloads: list[Path], non_imported: list[Path]):
        self._hide_loading()
        self._import_flow._set_data(all_downloads, non_imported)
        self._stack.setCurrentWidget(self._import_flow)

    def _load_stale_page(self):
        self._stack.setCurrentWidget(self._stale_flow)
        self._previous_page = "stale"
        worker = self._start_scan(message="Checking for stale comments...")
        worker.songs_ready.connect(self._on_stale_data)
        worker.error_occurred.connect(lambda e: self.show_toast(f"Error: {e}", "error"))
        worker.start()

    def _on_stale_data(self, songs: list[dict]):
        self._hide_loading()
        self._stale_flow.set_data(songs)
        self._stack.setCurrentWidget(self._stale_flow)

    def _load_rate_page(self):
        self._stack.setCurrentWidget(self._rate_flow)
        self._previous_page = "rate"
        worker = self._start_scan(message="Loading songs for rating...")
        worker.songs_ready.connect(self._on_rate_data)
        worker.error_occurred.connect(lambda e: self.show_toast(f"Error: {e}", "error"))
        worker.start()

    def _on_rate_data(self, songs: list[dict]):
        self._hide_loading()
        self._rate_flow.set_data(songs)
        self._stack.setCurrentWidget(self._rate_flow)

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

    def _refresh_channel_mgr(self):
        channels = get_channel_dirs(self._config.music_root)
        blocked = [
            c for c in channels if is_channel_blocked(self._config.music_root, c)
        ]
        self._channel_mgr.load(self._config.music_root, channels, blocked)
