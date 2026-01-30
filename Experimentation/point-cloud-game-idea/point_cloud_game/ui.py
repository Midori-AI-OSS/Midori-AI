from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QStackedLayout
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from config import CONFIG
from point_cloud_game.game import Game
from point_cloud_game.sim_adapter import PointCloudManager
from point_cloud_game.profile import ProfilerController
from point_cloud_game.gl_widget import WeaveGLWidget


class OverlayMenu(QFrame):
    def __init__(self, parent=None, on_new_game=None, on_exit=None, title_text: str = "POINT CLOUD\nGAME"):
        super().__init__(parent)
        self.on_new_game = on_new_game
        self.on_exit = on_exit
        
        self.setStyleSheet("background-color: rgba(20, 20, 30, 220); border-radius: 20px;")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Title
        self.title = QLabel(title_text)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color: #00ffff; font-size: 32px; font-weight: bold; background: transparent;")
        layout.addWidget(self.title)
        
        # Buttons
        btn_style = """
            QPushButton {
                background-color: rgba(0, 255, 255, 30);
                color: white;
                border: 2px solid cyan;
                border-radius: 10px;
                padding: 10px 30px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 255, 80);
            }
        """
        
        self.btn_new = QPushButton("NEW GAME")
        self.btn_new.setStyleSheet(btn_style)
        self.btn_new.clicked.connect(self._on_new_game_clicked)
        layout.addWidget(self.btn_new)
        
        self.btn_load = QPushButton("LOAD GAME")
        self.btn_load.setStyleSheet(btn_style)
        self.btn_load.setEnabled(False) # Prototype stub
        layout.addWidget(self.btn_load)
        
        self.btn_settings = QPushButton("SETTINGS")
        self.btn_settings.setStyleSheet(btn_style)
        layout.addWidget(self.btn_settings)
        
        self.btn_exit = QPushButton("EXIT")
        self.btn_exit.setStyleSheet(btn_style)
        self.btn_exit.clicked.connect(self._on_exit_clicked)
        layout.addWidget(self.btn_exit)

    def set_title(self, text: str) -> None:
        self.title.setText(text)

    def _on_new_game_clicked(self):
        if self.on_new_game:
            self.on_new_game()
            
    def _on_exit_clicked(self):
        if self.on_exit:
            self.on_exit()


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
        
        # Stack Layout? No, Overlay.
        # Use a resizeEvent on container or just absolute positioning
        
        self.layout = QStackedLayout(container)
        self.layout.setStackingMode(QStackedLayout.StackAll)
        
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
        self.layout.addWidget(self.gl_widget)
        
        # 2. UI Layer (Top)
        # We need a container for the menu to center it
        self.ui_container = QWidget()
        self.ui_container.setAttribute(Qt.WA_TranslucentBackground)
        self.ui_container.setStyleSheet("background: transparent;")
        self.ui_container.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Catch clicks
        ui_layout = QVBoxLayout(self.ui_container)
        ui_layout.setAlignment(Qt.AlignCenter)
        
        self.menu = OverlayMenu(
            on_new_game=self.start_game,
            on_exit=self.close,
        )
        self.menu.setFixedSize(300, 400)
        ui_layout.addWidget(self.menu)

        self.hud = QLabel(self.ui_container)
        self.hud.setAttribute(Qt.WA_TranslucentBackground)
        self.hud.setStyleSheet("color: rgba(235, 240, 255, 225); font-size: 14px; background: transparent;")
        self.hud.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.hud.move(12, 38)
        self.hud.raise_()

        self.spawn_bar = SpawnBar(self.ui_container)
        self.spawn_bar.setFixedHeight(int(CONFIG.ui.spawn_bar_height_px))
        self.spawn_bar.setFixedWidth(self.width() - int(CONFIG.ui.spawn_bar_margin_px) * 2)
        self.spawn_bar.move(int(CONFIG.ui.spawn_bar_margin_px), int(CONFIG.ui.spawn_bar_margin_px))
        self.spawn_bar.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.spawn_bar.raise_()
        self.spawn_bar.show()

        self.ui_container.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.ui_container.raise_()

        self.layout.addWidget(self.ui_container)
        
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._tick_ui)
        self._ui_timer.start(50)
        
    def start_game(self):
        self.game.reset()
        self.game.paused = False
        self.menu.set_title("POINT CLOUD\nGAME")
        self.menu.hide()

    def _tick_ui(self) -> None:
        self.hud.setText(
            f"HP: {int(self.game.player_hp):d}\n"
            f"Foes: {len(self.game.foes):d}  "
            f"Spawn: {self.game.spawn_timer:.2f}/{self.game.spawn_rate:.2f}"
        )
        if self.game.paused or self.game.is_game_over or self.game.spawn_rate <= 0.0:
            self.spawn_bar.set_progress(0.0)
        else:
            self.spawn_bar.set_progress(1.0 - max(0.0, min(1.0, self.game.spawn_timer / self.game.spawn_rate)))
        if self.game.is_game_over and not self.menu.isVisible():
            self.menu.set_title("GAME OVER")
            self.menu.show()
