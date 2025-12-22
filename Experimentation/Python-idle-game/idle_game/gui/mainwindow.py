from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QScrollArea, QGridLayout, QLabel, QPushButton,
                               QFrame, QHBoxLayout)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon
from idle_game.core.game_state import GameState
from idle_game.gui.character_window import CharacterWindow
from idle_game.gui.fight_window import FightWindow
from pathlib import Path

class CharacterCard(QFrame):
    clicked = Signal(str)

    def __init__(self, character_data, game_state, parent=None):
        super().__init__(parent)
        self.character_data = character_data
        self.game_state = game_state
        self.char_id = character_data["id"]
        
        self.setFixedSize(160, 240)
        self.setCursor(Qt.PointingHandCursor)
        
        self.base_style = """
            CharacterCard {
                background-color: #2c3e50;
                border: 2px solid #34495e;
                border-radius: 10px;
            }
            CharacterCard:hover {
                background-color: #34495e;
                border: 2px solid #3498db;
            }
        """
        self.selected_style = """
            CharacterCard {
                background-color: #34495e;
                border: 2px solid #e67e22;
                border-radius: 10px;
            }
            CharacterCard:hover {
                border: 2px solid #f39c12;
            }
        """
        self.setStyleSheet(self.base_style)
        
        layout = QVBoxLayout(self)
        
        # Portrait
        self.portrait_label = QLabel()
        self.portrait_label.setAlignment(Qt.AlignCenter)
        self.portrait_label.setFixedSize(130, 130)
        self.portrait_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.portrait_label.setStyleSheet("background-color: #333; border-radius: 5px; border: none;")
        
        portrait_path = character_data.get("ui", {}).get("portrait")
        if portrait_path and Path(portrait_path).exists():
             pixmap = QPixmap(portrait_path)
             self.portrait_label.setPixmap(pixmap.scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
             self.portrait_label.setText("No Image")
        
        layout.addWidget(self.portrait_label)
        
        # Name
        name_label = QLabel(character_data.get("name", "Unknown"))
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold; color: white;")
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(name_label)
        
        # Level / Info
        self.info_label = QLabel(f"Lvl {character_data['runtime']['level']}")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #bdc3c7;")
        self.info_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.info_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.char_id)
        super().mousePressEvent(event)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet(self.selected_style)
        else:
            self.setStyleSheet(self.base_style)

class MainWindow(QMainWindow):
    def __init__(self, game_state: GameState):
        super().__init__()
        self.game_state = game_state
        self.setWindowTitle("Mirai Idle Game")
        self.resize(1000, 800)
        
        from idle_game.core.save_manager import SaveManager
        pos = SaveManager.load_setting("win_pos_main")
        if pos:
            self.move(pos[0], pos[1])
        self.character_windows = {} # Keep references
        
        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Header Area
        header_layout = QHBoxLayout()
        
        self.header_label = QLabel("Idle Roster - Tick: 0")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(self.header_label)
        
        header_layout.addStretch()
        
        self.launch_btn = QPushButton("Launch Party Windows")
        self.launch_btn.clicked.connect(self.launch_party)
        header_layout.addWidget(self.launch_btn)
        
        main_layout.addLayout(header_layout)
        
        # Roster Grid Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        self.roster_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Signals
        self.game_state.characters_loaded.connect(self.populate_roster)
        self.game_state.tick_update.connect(self.update_header)
        self.game_state.start_duel.connect(self.launch_duel)
        
        # Initial population if data already loaded
        if self.game_state.characters:
            self.populate_roster()

    def populate_roster(self):
        # Clear existing
        for i in range(self.roster_layout.count()):
            item = self.roster_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        characters = self.game_state.characters
        row, col = 0, 0
        max_cols = 5
        
        for char in characters:
            if char.get("ui", {}).get("non_selectable"):
                continue
                
            card = CharacterCard(char, self.game_state)
            self.roster_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def update_header(self, tick_count):
        self.header_label.setText(f"Idle Roster - Tick: {tick_count} | Party: {len(self.game_state.active_party)}/5")

    def launch_party(self):
        # Close existing windows that aren't in party anymore
        active_ids = self.game_state.active_party
        to_close = [cid for cid in self.character_windows if cid not in active_ids]
        for cid in to_close:
            self.character_windows[cid].close()
            del self.character_windows[cid]
            
        # Open new windows
        for char_id in active_ids:
            if char_id not in self.character_windows:
                char_data = self.game_state.characters_map.get(char_id)
                if char_data:
                    window = CharacterWindow(char_data, self.game_state)
                    window.show()
                    self.character_windows[char_id] = window
            else:
                # Bring to front if already open
                self.character_windows[char_id].show()
                self.character_windows[char_id].activateWindow()

    def launch_duel(self, char1_id, char2_id):
        # Create Fight Window
        c1 = self.game_state.characters_map.get(char1_id)
        c2 = self.game_state.characters_map.get(char2_id)
        
        if c1 and c2:
            self.fight_window = FightWindow(c1, c2, self.game_state)
            self.fight_window.finished.connect(self._on_duel_finished)
            self.fight_window.show()

    def _on_duel_finished(self):
        self.fight_window = None

    def moveEvent(self, event):
        if self.isVisible():
            from idle_game.core.save_manager import SaveManager
            SaveManager.save_setting("win_pos_main", [self.x(), self.y()])
        super().moveEvent(event)



