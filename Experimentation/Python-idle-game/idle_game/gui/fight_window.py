from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFrame, QProgressBar)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, Signal
from PySide6.QtGui import QPixmap, QFont
from pathlib import Path
from idle_game.core.save_manager import SaveManager
import random

class FightWindow(QWidget):
    finished = Signal()

    def __init__(self, char1_data, char2_data, game_state):
        super().__init__()
        self.char1 = char1_data
        self.char2 = char2_data
        self.game_state = game_state
        
        self.p1_hp = 100
        self.p2_hp = 100
        
        self.setWindowTitle(f"DUEL: {char1_data['name']} vs {char2_data['name']}")
        self.setFixedSize(1600, 600) # Even longer and slightly shorter
        self.setStyleSheet("background-color: #1a1a1a; color: white;")
        
        self._pos_restored = False
        
        main_layout = QVBoxLayout(self)
        
        # Battle Area
        battle_layout = QHBoxLayout()
        battle_layout.setContentsMargins(40, 40, 40, 40)
        battle_layout.setSpacing(30)
        
        # Char 1 Group (Stats on Left)
        p1_group = QHBoxLayout()
        self.p1_stats = self._create_stats_panel(char1_data, "left")
        p1_group.addWidget(self.p1_stats)
        self.p1_frame = self._create_char_frame(char1_data)
        p1_group.addWidget(self.p1_frame)
        battle_layout.addLayout(p1_group)
        
        battle_layout.addStretch()
        
        # VS Label
        vs_label = QLabel("VS")
        vs_label.setFont(QFont("Arial", 48, QFont.Bold))
        vs_label.setStyleSheet("color: #e74c3c;")
        battle_layout.addWidget(vs_label)
        
        battle_layout.addStretch()
        
        # Char 2 Group (Stats on Right)
        p2_group = QHBoxLayout()
        self.p2_frame = self._create_char_frame(char2_data)
        p2_group.addWidget(self.p2_frame)
        self.p2_stats = self._create_stats_panel(char2_data, "right")
        p2_group.addWidget(self.p2_stats)
        battle_layout.addLayout(p2_group)
        
        main_layout.addLayout(battle_layout)
        
        # Combat Log / Status
        self.log_label = QLabel("Get ready to Rumble!")
        self.log_label.setAlignment(Qt.AlignCenter)
        self.log_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.log_label.setStyleSheet("color: #f1c40f; margin-bottom: 10px;")
        main_layout.addWidget(self.log_label)
        
        # Close Button (hidden initially)
        self.close_btn = QPushButton("FINISH")
        self.close_btn.setStyleSheet("background-color: #2ecc71; font-weight: bold; padding: 15px; font-size: 18px;")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setVisible(False)
        main_layout.addWidget(self.close_btn)
        
        # Animation Elements
        self.bits = []
        
        # Combat Timer
        self.combat_timer = QTimer()
        self.combat_timer.timeout.connect(self._combat_step)
        
        QTimer.singleShot(1500, lambda: self.combat_timer.start(800))

    def _create_stats_panel(self, data, side):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10) # Increased spacing
        
        stats = data["base_stats"]
        runtime = data["runtime"]
        level = runtime["level"]
        
        # Identity Header
        name_lbl = QLabel(data.get("name", "Unknown"))
        name_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #ecf0f1;")
        if side == "right": name_lbl.setAlignment(Qt.AlignRight)
        layout.addWidget(name_lbl)
        
        lvl_lbl = QLabel(f"Level {level}")
        lvl_lbl.setStyleSheet("font-size: 14px; color: #bdc3c7; margin-bottom: 5px;")
        if side == "right": lvl_lbl.setAlignment(Qt.AlignRight)
        layout.addWidget(lvl_lbl)

        # Mirror alignment for labels
        align_right = (side == "right")

        # Create Bars (using helpers)
        hp_bar = self._create_bar("HEALTH", "#e74c3c", layout, align_right)
        atk_bar = self._create_bar("ATK", "#3498db", layout, align_right)
        
        crit_r, crit_d = self._create_split_bar("Crit Rate", "#e67e22", "Crit Dmg", "#c0392b", layout, side)
        def_b, mit_b = self._create_split_bar("Defense", "#9b59b6", "Mitigation", "#7f8c8d", layout, side)
        
        dodge_b = self._create_bar("DODGE", "#16a085", layout, align_right)
        regen_b = self._create_bar("REGEN", "#2ecc71", layout, align_right)

        # Store references for updates
        if side == "left":
            self.p1_hp_bar = hp_bar
            self.p1_bars = {"atk": atk_bar, "crit_r": crit_r, "crit_d": crit_d, "def": def_b, "mit": mit_b, "dodge": dodge_b, "regen": regen_b}
        else:
            self.p2_hp_bar = hp_bar
            self.p2_bars = {"atk": atk_bar, "crit_r": crit_r, "crit_d": crit_d, "def": def_b, "mit": mit_b, "dodge": dodge_b, "regen": regen_b}

        # Initialize values
        hp_bar.setRange(0, 100)
        hp_bar.setValue(100)
        
        atk = stats.get("atk", 10) + (level * 2)
        atk_bar.setRange(0, 1000)
        atk_bar.setValue(int(atk))
        atk_bar.setFormat(f"{atk:.2f}")

        crit_r.setRange(0, 100); crit_r.setValue(int(stats.get("crit_rate", 0)*100)); crit_r.setFormat(f"{stats.get('crit_rate',0)*100:.2f}%")
        crit_d.setRange(0, 300); crit_d.setValue(int(stats.get("crit_damage", 1.5)*100)); crit_d.setFormat(f"{stats.get('crit_damage',1.5)*100:.2f}%")
        
        def_v = stats.get("defense",0) + level; def_b.setRange(0, 500); def_b.setValue(int(def_v)); def_b.setFormat(f"{def_v:.2f}")
        mit_v = stats.get("mitigation",0); mit_b.setRange(0, 100); mit_b.setValue(int(mit_v*10)); mit_b.setFormat(f"{mit_v:.2f}")
        
        dodge_v = stats.get("dodge_odds",0); dodge_b.setRange(0, 100); dodge_b.setValue(int(dodge_v*100)); dodge_b.setFormat(f"{dodge_v*100:.2f}%")
        regen_v = stats.get("regain",0); regen_b.setRange(0, 100); regen_b.setValue(int(regen_v)); regen_b.setFormat(f"{regen_v:.2f}")

        layout.addStretch()
        return container

    def _create_bar(self, label_text, color, parent_layout, align_right):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; font-size: 10px; color: #95a5a6;")
        if align_right: label.setAlignment(Qt.AlignRight)
        layout.addWidget(label)
        
        bar = QProgressBar()
        bar.setFixedSize(260, 22)
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #34495e;
                border-radius: 4px;
                text-align: center;
                background-color: #2c3e50;
                color: white;
                font-size: 9px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(bar)
        parent_layout.addWidget(container)
        return bar

    def _create_split_bar(self, label1, color1, label2, color2, parent_layout, side):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        l1 = QLabel(label1); l1.setStyleSheet("font-weight: bold; font-size: 10px; color: #95a5a6;")
        l2 = QLabel(label2); l2.setStyleSheet("font-weight: bold; font-size: 10px; color: #95a5a6;"); l2.setAlignment(Qt.AlignRight)
        header_layout.addWidget(l1); header_layout.addWidget(l2)
        layout.addLayout(header_layout)

        bar_container = QWidget()
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0); bar_layout.setSpacing(0)
        
        b1 = QProgressBar()
        b1.setInvertedAppearance(True)
        b1.setFixedSize(130, 22)
        b1.setStyleSheet(f"""
            QProgressBar {{ border: 2px solid #34495e; border-right: 1px; border-top-left-radius: 4px; border-bottom-left-radius: 4px;
                           text-align: center; background-color: #2c3e50; color: white; font-size: 9px; }}
            QProgressBar::chunk {{ background-color: {color1}; border-top-left-radius: 2px; border-bottom-left-radius: 2px; }}
        """)
        
        b2 = QProgressBar()
        b2.setFixedSize(130, 22)
        b2.setStyleSheet(f"""
            QProgressBar {{ border: 2px solid #34495e; border-left: 1px; border-top-right-radius: 4px; border-bottom-right-radius: 4px;
                           text-align: center; background-color: #2c3e50; color: white; font-size: 9px; }}
            QProgressBar::chunk {{ background-color: {color2}; border-top-right-radius: 2px; border-bottom-right-radius: 2px; }}
        """)
        
        bar_layout.addWidget(b1); bar_layout.addWidget(b2)
        layout.addWidget(bar_container)
        parent_layout.addWidget(container)
        return b1, b2

    def _create_char_frame(self, data):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        
        img_label = QLabel()
        img_label.setFixedSize(280, 360) # Slightly larger portraits
        img_label.setStyleSheet("border: 3px solid #555; border-radius: 12px; background-color: #222;")
        img_label.setAlignment(Qt.AlignCenter)
        
        portrait = data.get("ui", {}).get("portrait")
        if portrait and Path(portrait).exists():
            pixmap = QPixmap(portrait)
            img_label.setPixmap(pixmap.scaled(220, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img_label.setText("No Image")
            
        layout.addWidget(img_label)
        
        name_label = QLabel(data.get("name", "Unknown"))
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(name_label)
        
        return frame

    def _combat_step(self):
        # Determine attacker/defender
        attacker_idx = random.choice([1, 2])
        if attacker_idx == 1:
            atkr, dfndr = self.char1, self.char2
            dfndr_hp, dfndr_bar = self.p2_hp, self.p2_hp_bar
            side = "left"
        else:
            atkr, dfndr = self.char2, self.char1
            dfndr_hp, dfndr_bar = self.p1_hp, self.p1_hp_bar
            side = "right"

        # Regen Step (Half regain per combat tick)
        self.p1_hp = min(100, self.p1_hp + (self.char1["base_stats"].get("regain", 0) / 2))
        self.p2_hp = min(100, self.p2_hp + (self.char2["base_stats"].get("regain", 0) / 2))
        self.p1_hp_bar.setValue(int(self.p1_hp))
        self.p2_hp_bar.setValue(int(self.p2_hp))

        # --- Damage Logic ---
        atkr_stats = atkr["base_stats"]
        dfndr_stats = dfndr["base_stats"]
        atkr_lvl = atkr["runtime"]["level"]
        
        # 1. Dodge Check
        dodge_chance = dfndr_stats.get("dodge_odds", 0)
        if random.random() < dodge_chance:
            self.log_label.setText(f"{dfndr['name']} DODGED the attack!")
            self.log_label.setStyleSheet("color: #3498db; font-weight: bold; font-size: 16px;")
            self._spawn_projectile("MISS!", self._get_center(atkr_idx), self._get_center(3-attacker_idx))
            return

        # 2. Base Damage
        base_dmg = atkr_stats.get("atk", 10) * (1 + atkr_lvl / 50)
        
        # 3. Crit Check
        crit_chance = atkr_stats.get("crit_rate", 0)
        is_crit = random.random() < crit_chance
        if is_crit:
            base_dmg *= atkr_stats.get("crit_damage", 1.5)
            
        # 4. Mitigation & Defense
        # Mitigation is raw reduction factor? (Based on game_state calculation, it seems like a small float)
        mitigation = dfndr_stats.get("mitigation", 0)
        mitigated_dmg = base_dmg * (1 - min(0.8, mitigation / 100)) # Cap at 80% reduction
        
        defense = dfndr_stats.get("defense", 0)
        final_dmg = max(5, mitigated_dmg - (defense / 2))
        final_dmg *= random.uniform(0.9, 1.1)
        
        # Apply Damage
        damage = int(final_dmg / 10) # Scale to 100 HP bar
        if attacker_idx == 1:
            self.p2_hp = max(0, self.p2_hp - damage)
            self.p2_hp_bar.setValue(int(self.p2_hp))
        else:
            self.p1_hp = max(0, self.p1_hp - damage)
            self.p1_hp_bar.setValue(int(self.p1_hp))

        # Feedback
        log_text = f"{atkr['name']} deals {damage} damage!"
        if is_crit:
            log_text = f"CRITICAL! {log_text}"
            self.log_label.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 18px;")
        else:
            self.log_label.setStyleSheet("color: #f1c40f; font-weight: bold; font-size: 16px;")
            
        self.log_label.setText(log_text)
        
        text = "CRIT!" if is_crit else random.choice(["BIT!", "BITE!", "NIBBLE!", "PIXEL!"])
        self._spawn_projectile(text, self._get_center(attacker_idx), self._get_center(3-attacker_idx))
        
        # Check Win Condition
        if self.p1_hp <= 0 or self.p2_hp <= 0:
            self.combat_timer.stop()
            self._end_fight()

    def _get_center(self, char_idx):
        if char_idx == 1:
            return self.p1_frame.geometry().center()
        return self.p2_frame.geometry().center()


    def _end_fight(self):
        if self.p1_hp > 0:
            winner, loser = self.char1, self.char2
        else:
            winner, loser = self.char2, self.char1

        self.log_label.setText(f"VICTORY: {winner['name']} wins!")
        self.log_label.setStyleSheet("color: #2ecc71; font-size: 20px; font-weight: bold;")
        
        # Process Results
        self.game_state.process_combat_win(winner["id"])
        self.game_state.process_combat_loss(loser["id"])
        
        self.close_btn.setVisible(True)

    def _spawn_projectile(self, text, start, end):

        label = QLabel(text, self)
        label.setStyleSheet("color: #f1c40f; font-weight: bold;")
        label.setAttribute(Qt.WA_DeleteOnClose)
        label.show()
        
        anim = QPropertyAnimation(label, b"pos")
        anim.setDuration(400)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.finished.connect(label.close)
        anim.start()
        self.bits.append(anim) # Keep ref

    def moveEvent(self, event):
        if self.isVisible():
            SaveManager.save_setting("win_pos_fight", [self.x(), self.y()])
        super().moveEvent(event)

    def showEvent(self, event):
        if not self._pos_restored:
            pos = SaveManager.load_setting("win_pos_fight")
            if pos:
                self.move(pos[0], pos[1])
            self._pos_restored = True
        super().showEvent(event)

    def closeEvent(self, event):
        self.finished.emit()
        super().closeEvent(event)
