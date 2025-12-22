from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QScrollArea, QGridLayout, QLabel, QPushButton,
                               QFrame, QHBoxLayout, QSpinBox, QCheckBox)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon
from idle_game.core.game_state import GameState
from idle_game.gui.character_window import CharacterWindow
from idle_game.gui.fight_window import FightWindow
from idle_game.gui.widgets import PulseProgressBar
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
        
        # EXP Bar
        self.exp_bar = PulseProgressBar()
        self.exp_bar.setFixedHeight(8)
        self.exp_bar.setTextVisible(False)
        self.exp_bar.setStyleSheet("""
            QProgressBar {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #f1c40f;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.exp_bar)
        
        # Name
        self.name_label = QLabel(character_data.get("name", "Unknown"))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold; color: white;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.name_label)
        
        # Level / Info
        self.info_label = QLabel(f"Lvl {character_data['runtime']['level']}")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #bdc3c7;")
        self.info_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.info_label)

        # Initial Update
        self.update_stats()
        # Connect to tick
        self.game_state.tick_update.connect(self.update_stats)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.char_id)
        super().mousePressEvent(event)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet(self.selected_style)
        else:
            self.setStyleSheet(self.base_style)

    def update_stats(self, tick=0):
        # Always fetch latest data from map to be safe
        char = self.game_state.characters_map.get(self.char_id)
        if not char: return
        
        runtime = char["runtime"]
        level = runtime["level"]
        exp = runtime["exp"]
        max_exp = runtime.get("next_req", 30)
        
        self.info_label.setText(f"Lvl {level}")
        self.exp_bar.setRange(0, int(max_exp))
        self.exp_bar.setValue(int(exp))

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
        self.active_char_window = None # Single active window
        self.cards = {} # Track card widgets for highlighting
        
        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # Outer Horizontal Layout
        outer_layout = QHBoxLayout(central_widget)
        
        # LEFT: Main Roster Area
        roster_container = QWidget()
        roster_main_v = QVBoxLayout(roster_container)
        roster_main_v.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(roster_container, stretch=4) # Roster takes more space
        
        # Header Area (Inside Roster Area)
        header_layout = QHBoxLayout()
        self.header_label = QLabel("Idle Roster - Tick: 0")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(self.header_label)
        roster_main_v.addLayout(header_layout)
        
        # Roster Grid Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        self.roster_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)
        roster_main_v.addWidget(scroll_area)

        # RIGHT: Mods Panel
        mods_panel = QFrame()
        mods_panel.setFixedWidth(200)
        mods_panel.setStyleSheet("background-color: #2c3e50; border-left: 2px solid #34495e;")
        mods_layout = QVBoxLayout(mods_panel)
        mods_layout.setAlignment(Qt.AlignTop)
        
        mods_title = QLabel("MODS")
        mods_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ecf0f1; margin-bottom: 10px;")
        mods_layout.addWidget(mods_title)
        
        # Shared EXP Mod
        self.shared_exp_btn = QPushButton("Shared EXP: OFF")
        self.shared_exp_btn.setCheckable(True)
        self.shared_exp_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: 2px solid #2980b9;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #2ecc71;
                border: 2px solid #27ae60;
            }
        """)
        self.shared_exp_btn.clicked.connect(self.toggle_shared_exp)
        mods_layout.addWidget(self.shared_exp_btn)
        
        # Helper text
        self.shared_help = QLabel("Gain: 1% Potential / viewed char")
        self.shared_help.setWordWrap(True)
        self.shared_help.setStyleSheet("color: #95a5a6; font-size: 10px; margin-top: 5px; margin-bottom: 15px;")
        mods_layout.addWidget(self.shared_help)
        
        # Risk & Reward Mod
        rr_title = QLabel("Risk & Reward")
        rr_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ecf0f1; margin-top: 10px;")
        mods_layout.addWidget(rr_title)
        
        self.rr_toggle = QCheckBox("Enabled")
        self.rr_toggle.setStyleSheet("color: white; font-size: 11px;")
        self.rr_toggle.clicked.connect(self.toggle_risk_reward)
        mods_layout.addWidget(self.rr_toggle)
        
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Lvl:"))
        self.rr_level = QSpinBox()
        self.rr_level.setRange(1, 100)
        self.rr_level.setStyleSheet("background-color: #34495e; color: white;")
        self.rr_level.valueChanged.connect(self.update_risk_reward_level)
        level_row.addWidget(self.rr_level)
        mods_layout.addLayout(level_row)
        
        rr_help = QLabel("Boost: (Lvl+1)x EXP\nDrain: (1.5x Lvl) HP / 0.5s")
        rr_help.setWordWrap(True)
        rr_help.setStyleSheet("color: #95a5a6; font-size: 10px; margin-top: 5px;")
        mods_layout.addWidget(rr_help)
        
        outer_layout.addWidget(mods_panel)
        
        # Set initial UI state for mods
        self._update_mods_ui()
        
        # Signals
        self.game_state.characters_loaded.connect(self.populate_roster)
        self.game_state.tick_update.connect(self.update_header)
        self.game_state.start_duel.connect(self.launch_duel)
        
        # Initial population if data already loaded
        if self.game_state.characters:
            self.populate_roster()

    def populate_roster(self):
        # Clear existing
        self.cards.clear()
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
            card.clicked.connect(self.open_char_window)
            self.cards[char["id"]] = card
            self.roster_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def update_header(self, tick_count):
        self.header_label.setText(f"Idle Roster - Tick: {tick_count}")

    def _on_char_window_closed(self):
        # Clear all highlights
        for card in self.cards.values():
            card.update_style(False)
        self.active_char_window = None

    def open_char_window(self, char_id):
        # Update Highlighting
        for cid, card in self.cards.items():
            card.update_style(cid == char_id)

        # Close and clean up existing
        if self.active_char_window:
            try:
                self.active_char_window.close()
                self.active_char_window.deleteLater()
            except: pass
            
        char_data = self.game_state.characters_map.get(char_id)
        if char_data:
            self.active_char_window = CharacterWindow(char_data, self.game_state)
            self.active_char_window.closed.connect(self._on_char_window_closed)
            self.active_char_window.show()


    def launch_duel(self, char1_id, char2_id):
        # No need to close characters here as they are managed via active_char_window
        # but if one is open, maybe keep it? Or close it? 
        # User said "stay when theres a fights" previously. 
        # But now they say "only one char open at a time". 
        # This usually refers to the "Status" windows.
        
        # Create Fight Window
        c1 = self.game_state.characters_map.get(char1_id)
        c2 = self.game_state.characters_map.get(char2_id)
        
        if c1 and c2:
            self.fight_window = FightWindow(c1, c2, self.game_state)
            self.fight_window.finished.connect(self._on_duel_finished)
            self.fight_window.show()

    def _on_duel_finished(self):
        self.fight_window = None

    def toggle_shared_exp(self, checked):
        self.game_state.mods["shared_exp"] = checked
        self._update_mods_ui()
        self.game_state.save_game_state()

    def _update_mods_ui(self):
        active_shared = self.game_state.mods.get("shared_exp", False)
        self.shared_exp_btn.setChecked(active_shared)
        self.shared_exp_btn.setText(f"Shared EXP: {'ON' if active_shared else 'OFF'}")
        
        rr = self.game_state.mods.get("risk_reward", {})
        self.rr_toggle.setChecked(rr.get("enabled", False))
        self.rr_level.setValue(rr.get("level", 1))

    def toggle_risk_reward(self, checked):
        self.game_state.mods["risk_reward"]["enabled"] = checked
        self.game_state.save_game_state()

    def update_risk_reward_level(self, val):
        self.game_state.mods["risk_reward"]["level"] = val
        self.game_state.save_game_state()

    def moveEvent(self, event):
        if self.isVisible():
            from idle_game.core.save_manager import SaveManager
            SaveManager.save_setting("win_pos_main", [self.x(), self.y()])
        super().moveEvent(event)



