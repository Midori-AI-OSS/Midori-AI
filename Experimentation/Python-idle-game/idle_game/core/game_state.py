import json
from pathlib import Path
from typing import Dict, Any, List
from PySide6.QtCore import QObject, Signal, Slot, QTimer

class GameState(QObject):
    # Signal when character data is loaded
    characters_loaded = Signal()
    # Signal when a tick occurs, carrying the current tick count
    tick_update = Signal(int)

    def __init__(self):
        super().__init__()
        self.tick_count = 0
        self.characters: List[Dict[str, Any]] = []
        self.characters_map: Dict[str, Dict[str, Any]] = {}
        self.active_party: List[str] = [] # List of char IDs
        self.active_viewing_ids: set = set() # Set of char IDs currently being viewed

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000) # 1 second tick

    def start_viewing(self, char_id: str):
        self.active_viewing_ids.add(char_id)
        
    def stop_viewing(self, char_id: str):
        if char_id in self.active_viewing_ids:
            self.active_viewing_ids.remove(char_id)

    def load_characters(self):
        """Loads character data from the extracted JSON."""
        data_path = Path(__file__).parent.parent / "data" / "characters.json"
        
        if not data_path.exists():
            print(f"Error: Data file not found at {data_path}")
            return

        try:
            import random
            with open(data_path, "r", encoding="utf-8") as f:
                raw_characters_data = json.load(f)
            
            self.characters = []
            self.characters_map = {}

            for char in raw_characters_data:
                # Ensure metadata exists for randomization check
                char.setdefault("metadata", {})

                # Initializing runtime state for each character if not present
                char.setdefault("runtime", {
                    "level": 1,
                    "exp": 0,
                    "max_hp": char["base_stats"].get("max_hp", 1000),
                    "hp": char["base_stats"].get("max_hp", 1000)
                })
                # Ensure runtime hp is synced with max_hp if missing
                if "hp" not in char["runtime"]:
                     char["runtime"]["hp"] = char["runtime"]["max_hp"]
            
                # Stat Randomness (Variance)
                if "randomized" not in char["metadata"]:
                    for key in ["atk", "defense", "max_hp", "crit_rate", "crit_damage"]:
                        if key in char["base_stats"]:
                             # +/- 10%
                             variance = random.uniform(0.9, 1.1)
                             original = char["base_stats"][key]
                             if isinstance(original, int):
                                 char["base_stats"][key] = int(original * variance)
                             elif isinstance(original, float):
                                 char["base_stats"][key] = original * variance
                    char["metadata"]["randomized"] = True
                    # Update runtime max_hp if it was just randomized
                    char["runtime"]["max_hp"] = char["base_stats"].get("max_hp", 1000) + (char["runtime"]["level"] * 10)
                    if char["runtime"]["hp"] > char["runtime"]["max_hp"]:
                        char["runtime"]["hp"] = char["runtime"]["max_hp"]
                
                self.characters.append(char)
                self.characters_map[char["id"]] = char

            print(f"Loaded {len(self.characters)} characters.")
            self.characters_loaded.emit()
            
        except Exception as e:
            print(f"Failed to load characters: {e}")

    def _on_tick(self):
        """Called every second to update game state."""
        self.tick_count += 1
        self.tick_update.emit(self.tick_count)
        
        # Passive Growth: Experience gain every tick
        if not self.characters:
            self.load_characters()

        # Passive Growth: Experience gain every tick
        for char in self.characters:
            # Conditional EXP: Only gains if someone is viewing (active_viewing_ids)
            # The user requirement was "Chars exp should only tick when their window is open."
            # So check if char['id'] is in self.active_viewing_ids
            if char["id"] not in self.active_viewing_ids:
                continue

            runtime = char["runtime"]
            
            # --- Rebirth & Growth Logic ---
            # Default multipliers if not present
            exp_mult = runtime.get("exp_multiplier", 1.0)
            req_mult = runtime.get("req_multiplier", 1.0)
            
            # 1 EXP * Multiplier
            gain = 1 * exp_mult
            runtime["exp"] += gain
            
            # Level Up Logic
            # Base Exp Req = Level * 100
            # Scaled Exp Req = (Level * 100) * req_multiplier
            required_exp = (runtime["level"] * 100) * req_mult
            
            if runtime["exp"] >= required_exp:
                runtime["exp"] = 0
                runtime["level"] += 1
                runtime["max_hp"] += 10 # Growth
                runtime["hp"] = runtime["max_hp"]

    def rebirth_character(self, char_id: str):
        """Resets character to Level 1 with increased stats/multipliers."""
        char = self.characters_map.get(char_id)
        if not char:
            return False
            
        runtime = char["runtime"]
        if runtime["level"] < 50:
            return False
            
        print(f"Rebirthing {char_id}...")
        
        # Reset Stats
        runtime["level"] = 1
        runtime["exp"] = 0
        runtime["max_hp"] = char["base_stats"].get("max_hp", 1000)
        runtime["hp"] = runtime["max_hp"]
        
        # Apply Bonuses
        # +25% EXP Gain
        current_exp_mult = runtime.get("exp_multiplier", 1.0)
        runtime["exp_multiplier"] = current_exp_mult + 0.25
        
        # +5% EXP Required
        current_req_mult = runtime.get("req_multiplier", 1.0)
        runtime["req_multiplier"] = current_req_mult + 0.05
        
        # Track Rebirths
        runtime["rebirths"] = runtime.get("rebirths", 0) + 1
        
        return True
        
        # Autosave every 60 ticks
        if self.tick_count % 60 == 0:
            self.save_game_state()

    def save_game_state(self):
        from idle_game.core.save_manager import SaveManager
        SaveManager.save_game(self.characters)

    def load_game_state(self):
        from idle_game.core.save_manager import SaveManager
        SaveManager.load_game(self.characters)

    def toggle_party_member(self, char_id: str) -> bool:
        """Toggles a character in/out of the active party. Returns True if in party."""
        if char_id in self.active_party:
            self.active_party.remove(char_id)
            return False
        else:
            if len(self.active_party) < 5:
                self.active_party.append(char_id)
                return True
            return False


