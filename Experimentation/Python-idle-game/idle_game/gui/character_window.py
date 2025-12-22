from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from pathlib import Path

class CharacterWindow(QWidget):
    def __init__(self, character_data, game_state):
        super().__init__()
        self.character_data = character_data
        self.game_state = game_state
        self.char_id = character_data["id"]
        
        self.setWindowTitle(f"Status: {character_data.get('name', 'Unknown')}")
        # 16:9 Aspect Ratio (e.g., 800x450)
        self.setFixedSize(800, 450)
        
        # Main Horizontal Layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # --- LEFT SIDE: Portrait & Fight ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.portrait_label = QLabel()
        self.portrait_label.setAlignment(Qt.AlignCenter)
        self.portrait_label.setFixedSize(350, 410) # Adjust to fit height
        self.portrait_label.setStyleSheet("background-color: #222; border-radius: 10px; border: 2px solid #555;")
        
        portrait_path = character_data.get("ui", {}).get("portrait")
        if portrait_path and Path(portrait_path).exists():
             pixmap = QPixmap(portrait_path)
             # Scale to fill maximizing height
             self.portrait_label.setPixmap(pixmap.scaled(350, 410, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
             self.portrait_label.setText("No Image")
        left_layout.addWidget(self.portrait_label)

        # Fight / Cooldown Section
        self.fight_container = QWidget()
        self.fight_container.setFixedSize(350, 50)
        self.fight_container.setStyleSheet("background: transparent;")
        fight_stack = QVBoxLayout(self.fight_container)
        fight_stack.setContentsMargins(0, 5, 0, 0)

        # We create a bar that fills up over 2 minutes
        self.cooldown_bar = QProgressBar()
        self.cooldown_bar.setFixedSize(350, 45)
        self.cooldown_bar.setTextVisible(False)
        self.cooldown_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 8px;
                background-color: #222;
            }
            QProgressBar::chunk {
                background-color: #c0392b;
                border-radius: 6px;
            }
        """)
        
        # Button goes on top of the bar (we'll just use the bar + button layout)
        self.fight_btn = QPushButton("FIGHT")
        self.fight_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:disabled {
                color: #555;
            }
        """)
        self.fight_btn.clicked.connect(self.on_fight_click)
        
        # Overlay layout for the button on the bar
        overlay = QHBoxLayout(self.cooldown_bar)
        overlay.setContentsMargins(0, 0, 0, 0)
        overlay.addWidget(self.fight_btn)
        
        fight_stack.addWidget(self.cooldown_bar)
        left_layout.addWidget(self.fight_container)

        main_layout.addWidget(left_panel)
        
        # --- RIGHT SIDE: Stats ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop)
        
        # Name Header
        name_label = QLabel(character_data.get("name", "Unknown"))
        name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ecf0f1;")
        right_layout.addWidget(name_label)

        # Level Label
        self.level_label = QLabel(f"Level: {self._get_runtime('level')}")
        self.level_label.setStyleSheet("font-size: 18px; color: #bdc3c7; margin-bottom: 15px;")
        right_layout.addWidget(self.level_label)

        # Stats Bars
        self.hp_bar = self._create_bar("HP", "#e74c3c", right_layout)
        self.exp_bar = self._create_bar("EXP", "#f1c40f", right_layout)
        self.atk_bar = self._create_bar("ATK", "#3498db", right_layout)
        # self.def_bar = self._create_bar("DEF", "#9b59b6", right_layout) # Replaced by split bar

        self.crit_rate_bar, self.crit_dmg_bar = self._create_split_bar("Crit Rate", "#e67e22", "Crit Dmg", "#c0392b", right_layout)
        self.def_bar, self.mit_bar = self._create_split_bar("Defense", "#9b59b6", "Mitigation", "#7f8c8d", right_layout)
        self.dodge_bar = self._create_bar("Dodge", "#16a085", right_layout)
        # self.mit_bar = self._create_bar("Mitigation", "#7f8c8d", right_layout) # Replaced by split bar
        self.regen_bar = self._create_bar("Regen", "#2ecc71", right_layout)

        # Rebirth Button
        self.rebirth_btn = QPushButton("REBIRTH (Lvl 50)")
        self.rebirth_btn.setStyleSheet("background-color: #e67e22; font-weight: bold; color: white;")
        self.rebirth_btn.clicked.connect(self.on_rebirth_click)
        self.rebirth_btn.setVisible(False) # Hidden by default
        right_layout.addWidget(self.rebirth_btn)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)


        # Connect signals
        self.game_state.tick_update.connect(self.update_stats)
        
        self.update_stats(0) # Initial update
    
    def showEvent(self, event):
        self.game_state.start_viewing(self.char_id)
        super().showEvent(event)
        
    def closeEvent(self, event):
        self.game_state.stop_viewing(self.char_id)
        super().closeEvent(event)
    
    def on_rebirth_click(self):
        if self.game_state.rebirth_character(self.char_id):
            # Refresh immediately
            self.update_stats(0)

    def on_fight_click(self):
        self.game_state.init_duel(self.char_id)


    def _create_bar(self, label_text, color, parent_layout):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; font-size: 12px; color: #95a5a6;")
        layout.addWidget(label)
        
        bar = QProgressBar()
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #34495e;
                border-radius: 5px;
                text-align: center;
                height: 25px;
                background-color: #2c3e50;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(bar)
        
        parent_layout.addWidget(container)
        return bar

    def _create_split_bar(self, label1, color1, label2, color2, parent_layout):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # Header Labels (Side by Side)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        label_left = QLabel(label1)
        label_left.setStyleSheet("font-weight: bold; font-size: 12px; color: #95a5a6; min-height: 20px;")
        label_right = QLabel(label2)
        label_right.setStyleSheet("font-weight: bold; font-size: 12px; color: #95a5a6; min-height: 20px;")
        label_right.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(label_left)
        header_layout.addWidget(label_right)
        layout.addLayout(header_layout)

        # Split Bars Container
        bar_container = QWidget()
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        
        # Left Bar (Inverted)
        bar1 = QProgressBar()
        bar1.setInvertedAppearance(True)
        bar1.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #34495e;
                border-right: 1px solid #34495e; /* Share border */
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
                qproperty-alignment: AlignCenter;
                height: 25px;
                background-color: #2c3e50;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {color1};
                border-top-left-radius: 3px;
                border-bottom-left-radius: 3px;
            }}
        """)
        
        # Right Bar
        bar2 = QProgressBar()
        bar2.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #34495e;
                border-left: 1px solid #34495e; /* Share border */
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                qproperty-alignment: AlignCenter;
                height: 25px;
                background-color: #2c3e50;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {color2};
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
        """)
        
        bar_layout.addWidget(bar1)
        bar_layout.addWidget(bar2)
        layout.addWidget(bar_container)
        
        parent_layout.addWidget(container)
        return bar1, bar2

    def _get_runtime(self, key):
        return self.character_data["runtime"].get(key, 0)
    
    def _get_base(self, key):
        return self.character_data["base_stats"].get(key, 0)

    def update_stats(self, tick):
        runtime = self.character_data["runtime"]
        level = runtime["level"]
        hp = runtime["hp"]
        max_hp = runtime["max_hp"]
        exp = runtime["exp"]
        exp_mult = runtime.get("exp_multiplier", 1.0)
        req_mult = runtime.get("req_multiplier", 1.0)
        rebirths = runtime.get("rebirths", 0)
        
        # Use the stored next_req or falling back to the new base 30 logic
        max_exp = runtime.get("next_req", (30 * req_mult))
        
        # Update Labels
        title = f"Level: {level}"
        if rebirths > 0:
            title += f" (Rebirths: {rebirths})"
        self.level_label.setText(title)
        
        # Toggle Rebirth Button
        if level >= 50:
            self.rebirth_btn.setVisible(True)
            self.rebirth_btn.setEnabled(True)
        else:
            self.rebirth_btn.setVisible(False)

        self.hp_bar.setFormat(f"{int(hp)}/{int(max_hp)}")
        self.hp_bar.setRange(0, int(max_hp))
        self.hp_bar.setValue(int(hp))
        
        self.exp_bar.setFormat(f"{int(exp)}/{int(max_exp)}")
        self.exp_bar.setRange(0, int(max_exp))
        self.exp_bar.setValue(int(exp))

        atk = self._get_base("atk") + (level * 2) 
        defense = self._get_base("defense") + (level * 1)
        
        self.atk_bar.setFormat(f"{atk} (x{exp_mult:.2f} Exp)") # Show Exp Mult on ATK for now as debug/info? Or just assume hidden
        # Actually user didn't ask to see extra stats visually yet, just "show each bar". 
        # But showing the exp multiplier somewhere is nice. Let's put it on the EXP bar text? 
        # No, format is restricted. I'll leave it as is.
        
        self.atk_bar.setFormat(f"{atk}")
        self.atk_bar.setRange(0, 1000) 
        self.atk_bar.setValue(int(atk))
        
        # Defense (Left of split)
        self.def_bar.setFormat(f"{defense}")
        self.def_bar.setRange(0, 1000)
        self.def_bar.setValue(int(defense))
        
        # Update Extra Stats
        crit_rate = self._get_base("crit_rate")
        crit_dmg = self._get_base("crit_damage")
        dodge = self._get_base("dodge_odds")
        mitigation = self._get_base("mitigation")
        regen = self._get_base("regain")
        
        # Update Fight Button & Cooldown
        self._update_fight_ui()

        # Crit Rate (0-100%)
        self.crit_rate_bar.setFormat(f"{crit_rate*100:.1f}%")
        self.crit_rate_bar.setRange(0, 100)
        self.crit_rate_bar.setValue(int(crit_rate * 100))

        # Crit Damage (Usually > 100%, maybe cap at 300 visual?)
        # Fix: Ensure text is visible and format is clear
        self.crit_dmg_bar.setFormat(f"{crit_dmg*100:.0f}%")
        self.crit_dmg_bar.setRange(0, 300) 
        self.crit_dmg_bar.setValue(int(crit_dmg * 100))
        # self.crit_dmg_bar.setAlignment(Qt.AlignCenter) # Removed manual alignment to fix vertical offset

        # Dodge (0-100%)
        self.dodge_bar.setFormat(f"{dodge*100:.1f}%")
        self.dodge_bar.setRange(0, 100)
        self.dodge_bar.setValue(int(dodge * 100))

        # Mitigation (Right of split)
        # Assuming percent based for bar, but displaying raw value or formatted
        mit_percent = min(mitigation * 10, 100) # Arbitrary scaling for visuals
        self.mit_bar.setFormat(f"{mitigation:.2f}")
        self.mit_bar.setRange(0, 100)
        self.mit_bar.setValue(int(mit_percent))
        # self.mit_bar.setAlignment(Qt.AlignCenter)

        # Regen (Raw value)
        self.regen_bar.setFormat(f"{regen}")
        self.regen_bar.setRange(0, 100) # Assuming 100 is high regen
        self.regen_bar.setValue(int(regen))
    
    def _update_fight_ui(self):
        gs = self.game_state
        char_id = self.char_id
        current_tick = gs.tick_count
        
        # Check Boost
        has_boost = (char_id in gs.fight_boost_expiry and current_tick < gs.fight_boost_expiry[char_id])
        
        # Check Cooldown
        expiry = gs.fight_cooldown_expiry.get(char_id, 0)
        on_cooldown = current_tick < expiry
        
        if on_cooldown:
            self.fight_btn.setEnabled(False)
            total_duration = 1200 # 120s @ 10t/s
            remaining = expiry - current_tick
            progress = int(((total_duration - remaining) / total_duration) * 100)
            self.cooldown_bar.setValue(progress)
            self.fight_btn.setText(f"RECHARGING... ({remaining//10}s)")
        else:
            self.fight_btn.setEnabled(True)
            self.cooldown_bar.setValue(100)
            if has_boost:
                self.fight_btn.setText("BOOST ACTIVE! (2x EXP)")
                self.cooldown_bar.setStyleSheet("""
                    QProgressBar { border: 2px solid #555; border-radius: 8px; background-color: #222; }
                    QProgressBar::chunk { background-color: #f1c40f; border-radius: 6px; }
                """)
            else:
                self.fight_btn.setText("FIGHT")
                self.cooldown_bar.setStyleSheet("""
                    QProgressBar { border: 2px solid #555; border-radius: 8px; background-color: #222; }
                    QProgressBar::chunk { background-color: #c0392b; border-radius: 6px; }
                """)
