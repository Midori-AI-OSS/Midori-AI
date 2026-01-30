from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtGui import QShortcut
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QSizePolicy

from PySide6.QtCore import QEvent

from config import CONFIG
from point_cloud_game.game import Game
from point_cloud_game.sim_adapter import PointCloudManager
from point_cloud_game.profile import ProfilerController
from point_cloud_game.gl_widget import WeaveGLWidget
from point_cloud_game.settings import SettingsOverlay


class MenuOverlay(QWidget):
    def __init__(self, *, on_new_game, on_resume, on_settings, on_exit, parent=None) -> None:
        super().__init__(parent=parent)
        self._on_new_game = on_new_game
        self._on_resume = on_resume
        self._on_settings = on_settings
        self._on_exit = on_exit

        self.setObjectName("mainMenuPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("fullScreen", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.title = QLabel("Point Cloud Game")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 22px; font-weight: 850;")

        self.subtitle = QLabel("Prototype")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setProperty("role", "dim")

        layout.addStretch(2)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)

        self.buttons = QWidget(self)
        btns = QVBoxLayout(self.buttons)
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(8)
        btns.setAlignment(Qt.AlignHCenter)

        def _menu_button(text: str, *, on_click) -> QPushButton:
            b = QPushButton(text)
            b.setProperty("stainedMenu", "true")
            b.setMinimumHeight(44)
            b.clicked.connect(on_click)
            return b

        self.btn_resume = _menu_button("Resume", on_click=self._on_resume)
        self.btn_new = _menu_button("New Game", on_click=self._on_new_game)
        self.btn_settings = _menu_button("Settings", on_click=self._on_settings)
        self.btn_exit = _menu_button("Exit", on_click=self._on_exit)

        btns.addWidget(self.btn_resume)
        btns.addWidget(self.btn_new)
        btns.addWidget(self.btn_settings)
        btns.addWidget(self.btn_exit)

        layout.addWidget(self.buttons)
        layout.addStretch(3)

        self._mode = "title"
        self.set_mode("title")

    def set_mode(self, mode: str) -> None:
        mode = str(mode)
        self._mode = mode
        self.setProperty("mode", mode)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        if mode == "title":
            self.title.setText("Point Cloud Game")
            self.subtitle.setText("Press New Game to begin")
            self.btn_resume.hide()
            self.btn_new.show()
            self.btn_settings.show()
            self.btn_exit.show()
            return
        if mode == "pause":
            self.title.setText("Paused")
            self.subtitle.setText("Press Esc to resume")
            self.btn_resume.show()
            self.btn_new.show()
            self.btn_settings.show()
            self.btn_exit.show()
            return
        if mode == "game_over":
            self.title.setText("Game Over")
            self.subtitle.setText("Try again?")
            self.btn_resume.hide()
            self.btn_new.show()
            self.btn_settings.show()
            self.btn_exit.show()
            return
        raise ValueError(f"Unknown menu mode: {mode}")

    @property
    def mode(self) -> str:
        return str(self._mode)


class SpawnBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._progress = 0.0
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_progress(self, progress: float) -> None:
        p = float(max(0.0, min(1.0, progress)))
        if abs(p - self._progress) < 1e-6:
            return
        self._progress = p
        self.update()

    def _fill_color(self) -> QColor:
        p = float(self._progress)
        if p <= 0.5:
            t = p / 0.5
            r = int(round(40 + (255 - 40) * t))
            g = int(round(220 + (220 - 220) * t))
            b = int(round(80 + (40 - 80) * t))
            return QColor(r, g, b, 220)
        t = (p - 0.5) / 0.5
        r = 255
        g = int(round(220 + (70 - 220) * t))
        b = int(round(40 + (40 - 40) * t))
        return QColor(r, g, b, 220)

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        bg = QColor(10, 10, 14, 210)
        border = QColor(255, 255, 255, 120)
        p.setPen(border)
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        fill_w = int(round((w - 2) * float(self._progress)))
        if fill_w > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(self._fill_color())
            p.drawRoundedRect(1, 1, fill_w, h - 2, 4, 4)


class GameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Point Cloud Game Prototype")
        
        # Fixed Aspect Ratio Size (9:16)
        # 540x960 is good for 1080p screens
        self.setFixedSize(540, 960)
        
        # Central Container
        container = QWidget()
        self.setCentralWidget(container)

        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        # 1. Game Layer (Bottom)
        assets_dir = Path(__file__).parent / "assets"
        weave_path = assets_dir / "weave.png"
        
        self.manager = PointCloudManager()
        self.game = Game(self.manager, str(weave_path))
        self.profiler = ProfilerController()
        self.game.paused = True
        
        self.gl_widget = WeaveGLWidget(
            game=self.game,
            profiler=self.profiler
        )
        self.gl_widget.installEventFilter(self)
        root_layout.addWidget(self.gl_widget)
        
        # 2. UI Overlay (child of the GL widget so it reliably stacks on top)
        self.ui_overlay = QWidget(self.gl_widget)
        self.ui_overlay.setAttribute(Qt.WA_TranslucentBackground, True)
        self.ui_overlay.setStyleSheet("background: transparent;")
        self.ui_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.ui_overlay.setGeometry(self.gl_widget.rect())

        self.hud = QLabel(self.ui_overlay)
        self.hud.setAttribute(Qt.WA_TranslucentBackground)
        self.hud.setStyleSheet("color: rgba(235, 240, 255, 225); font-size: 14px; background: transparent;")
        self.hud.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.hud.move(12, 38)
        self.hud.raise_()

        self.spawn_bar = SpawnBar(self.ui_overlay)
        self.spawn_bar.setFixedHeight(int(CONFIG.ui.spawn_bar_height_px))
        self.spawn_bar.setFixedWidth(self.width() - int(CONFIG.ui.spawn_bar_margin_px) * 2)
        self.spawn_bar.move(int(CONFIG.ui.spawn_bar_margin_px), int(CONFIG.ui.spawn_bar_margin_px))
        self.spawn_bar.raise_()
        self.spawn_bar.show()

        self.menu_overlay = MenuOverlay(
            on_new_game=self.start_game,
            on_resume=self.resume_game,
            on_settings=self.show_settings,
            on_exit=self.close,
            parent=self.ui_overlay,
        )
        self.menu_overlay.setGeometry(self.ui_overlay.rect())
        self.menu_overlay.raise_()

        self.settings_overlay = SettingsOverlay(on_apply=self.apply_settings, on_close=self.hide_settings, parent=self.ui_overlay)
        self.settings_overlay.setGeometry(self.ui_overlay.rect())
        self.settings_overlay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.settings_overlay.hide()

        self.ui_overlay.raise_()

        self._title_screen = True
        self.gl_widget.set_scene_visible(False)
        self.menu_overlay.set_mode("title")
        self.menu_overlay.show()
        self.hud.hide()
        self.spawn_bar.hide()
        
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._tick_ui)
        self._ui_timer.start(50)

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._toggle_menu)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self._activate_primary)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self._activate_primary)

        QTimer.singleShot(0, self._sync_overlay_geometry)

        if os.environ.get("PCG_AUTOSTART", "").strip() == "1":
            QTimer.singleShot(0, self.start_game)
        if os.environ.get("PCG_SHOW_SETTINGS", "").strip() == "1":
            QTimer.singleShot(0, self.show_settings)
        
    def start_game(self):
        self._title_screen = False
        self.hide_settings()
        self.menu_overlay.hide()
        self.gl_widget.set_scene_visible(True)
        self.gl_widget.reset_sim()
        self.game.reset()
        self.apply_settings()
        self.game.paused = False
        self.hud.show()
        self.spawn_bar.show()

    def resume_game(self) -> None:
        if self._title_screen:
            return
        self.menu_overlay.hide()
        self.game.paused = False
        self.gl_widget.set_scene_visible(True)

    def apply_settings(self) -> None:
        self.game.apply_config(rescale_existing_foes=True)
        self.gl_widget.apply_config()

    def show_settings(self) -> None:
        self.game.paused = True
        self.menu_overlay.hide()
        self.settings_overlay.refresh_from_config()
        self.settings_overlay.show()
        self.settings_overlay.raise_()
        self.gl_widget.set_scene_visible(True)

    def hide_settings(self) -> None:
        self.settings_overlay.hide()
        if not self.game.is_game_over:
            if self._title_screen:
                self.menu_overlay.set_mode("title")
                self.menu_overlay.show()
                self.gl_widget.set_scene_visible(False)
                self.hud.hide()
                self.spawn_bar.hide()
            else:
                self.game.paused = False

    def _tick_ui(self) -> None:
        if self._title_screen:
            return
        self.hud.setText(
            f"HP: {int(self.game.player_hp):d}\n"
            f"Foes: {len(self.game.foes):d}  "
            f"Spawn: {self.game.spawn_timer:.2f}/{self.game.spawn_rate:.2f}"
        )
        if self.game.paused or self.game.is_game_over or self.game.spawn_rate <= 0.0:
            self.spawn_bar.set_progress(0.0)
        else:
            self.spawn_bar.set_progress(1.0 - max(0.0, min(1.0, self.game.spawn_timer / self.game.spawn_rate)))
        if self.game.is_game_over and not self.menu_overlay.isVisible():
            self.game.paused = True
            self.menu_overlay.set_mode("game_over")
            self.menu_overlay.show()
            self.menu_overlay.raise_()
            self.settings_overlay.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.spawn_bar.setFixedWidth(self.width() - int(CONFIG.ui.spawn_bar_margin_px) * 2)
        self._sync_overlay_geometry()

    def _sync_overlay_geometry(self) -> None:
        r = self.gl_widget.rect()
        self.ui_overlay.setGeometry(r)
        self.menu_overlay.setGeometry(self.ui_overlay.rect())
        self.settings_overlay.setGeometry(self.ui_overlay.rect())

    def eventFilter(self, watched, event) -> bool:
        if watched is self.gl_widget and event.type() == QEvent.Resize:
            self._sync_overlay_geometry()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_overlay_geometry)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key_Escape:
            if self.settings_overlay.isVisible():
                self.hide_settings()
            elif self.menu_overlay.isVisible():
                if self._title_screen:
                    event.accept()
                    return
                self.resume_game()
            else:
                if not self.game.is_game_over:
                    self.game.paused = True
                    self.menu_overlay.set_mode("pause")
                    self.menu_overlay.show()
                    self.menu_overlay.raise_()
            event.accept()
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.menu_overlay.isVisible():
                if self.menu_overlay.mode == "pause":
                    self.resume_game()
                else:
                    self.start_game()
                event.accept()
                return

        super().keyPressEvent(event)

    def _toggle_menu(self) -> None:
        if self.settings_overlay.isVisible():
            self.hide_settings()
            return

        if self.menu_overlay.isVisible():
            if self._title_screen:
                return
            self.resume_game()
            return

        if self._title_screen or self.game.is_game_over:
            return

        self.game.paused = True
        self.menu_overlay.set_mode("pause")
        self.menu_overlay.show()
        self.menu_overlay.raise_()
        self.gl_widget.set_scene_visible(True)

    def _activate_primary(self) -> None:
        if self._title_screen:
            self.start_game()
            return
        if self.menu_overlay.isVisible():
            if self.menu_overlay.mode == "pause":
                self.resume_game()
            elif self.menu_overlay.mode in ("title", "game_over"):
                self.start_game()
