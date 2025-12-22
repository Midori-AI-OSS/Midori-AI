import json
from pathlib import Path
from typing import Dict, Any, List
from PySide6.QtCore import QObject, Signal, Slot, QTimer

class GameState(QObject):
    # Signal when character data is loaded
    characters_loaded = Signal()
    # Signal when a tick occurs, carrying the current tick count
    tick_update = Signal(int)
    # Signal to start a duel: (char1_id, char2_id)
    start_duel = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.tick_count = 0
        self.characters: List[Dict[str, Any]] = []
        self.characters_map: Dict[str, Dict[str, Any]] = {}
        self.active_party: List[str] = [] # List of char IDs
        self.active_viewing_ids: set = set() # Set of char IDs currently being viewed
        
        # Combat Boosts & Cooldowns (stored as expiry tick count)
        self.fight_boost_expiry: Dict[str, int] = {}
        self.fight_debuff_expiry: Dict[str, int] = {}
        self.fight_cooldown_expiry: Dict[str, int] = {}
 
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(100) # 10 ticks per second (100ms)

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

                # Handle Random Image Selection (Folder support)
                portrait_path = char.get("ui", {}).get("portrait")
                if portrait_path:
                    p = Path(portrait_path)
                    if p.exists() and p.is_dir():
                        # It's a directory, pick a random PNG
                        pngs = list(p.glob("*.png"))
                        if pngs:
                            selected_img = random.choice(pngs)
                            # Update to specific file path for the UI to load
                            char["ui"]["portrait"] = str(selected_img)
                            # print(f"Selected random image for {char['id']}: {selected_img.name}")

            print(f"Loaded {len(self.characters)} characters.")
            self.load_game_state() # Apply saved progress
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
            
            # Fight Boost: 2x EXP if boost is active
            # Fight Debuff: 0.25x EXP if debuff is active
            combat_mult = 1.0
            if char["id"] in self.fight_boost_expiry:
                if self.tick_count < self.fight_boost_expiry[char["id"]]:
                    combat_mult *= 2.0
                else:
                    del self.fight_boost_expiry[char["id"]]

            if char["id"] in self.fight_debuff_expiry:
                if self.tick_count < self.fight_debuff_expiry[char["id"]]:
                    combat_mult *= 0.25
                else:
                    del self.fight_debuff_expiry[char["id"]]

            # 1 EXP * Multipliers
            gain = 1 * exp_mult * combat_mult
            runtime["exp"] += gain
            
            # Level Up Logic
            # NEW REQ: (Level * 30 * req_multiplier) +/- 5%
            if "next_req" not in runtime:
                import random
                runtime["next_req"] = (runtime["level"] * 30 * req_mult) * random.uniform(0.95, 1.05)
            
            if runtime["exp"] >= runtime["next_req"]:
                self.level_up_character(char)
                # Set up next level requirement
                import random
                runtime["next_req"] = (runtime["level"] * 30 * req_mult) * random.uniform(0.95, 1.05)
                self.save_game_state() # Save on level up

        # Autosave every 125 ticks
        if self.tick_count % 125 == 0:
            self.save_game_state()

    def level_up_character(self, char: Dict[str, Any]):
        """Increments level and applies weighted stat upgrades."""
        import random
        runtime = char["runtime"]
        runtime["level"] += 1
        runtime["exp"] = 0
        runtime["max_hp"] += 10
        runtime["hp"] = runtime["max_hp"]
        
        # Stat Upgrades
        # Points: 1 + (Level // 10)
        points = 1 + (runtime["level"] // 10)
        
        stat_keys = ["atk", "defense", "mitigation", "crit_rate", "crit_damage", "dodge_odds", "regain"]
        base_stats = char["base_stats"]
        
        # Create weights based on current stats
        # We need to normalize them since some are [0,1] and some are [10, 1000]
        weights = []
        for key in stat_keys:
            val = base_stats.get(key, 0.1)
            # Scaling factors to make smaller stats relevant
            if key in ["crit_rate", "dodge_odds", "mitigation"]: # Usually small values
                weights.append(val * 100)
            elif key == "crit_damage": # 1.5 -> 15
                weights.append(val * 10)
            else:
                weights.append(val)
        
        # Ensure no zero weights
        weights = [max(0.1, w) for w in weights]
        
        # Pick stats to upgrade
        chosen_stats = random.choices(stat_keys, weights=weights, k=points)
        
        for s_key in chosen_stats:
            # Upgrade by 0.1%
            current_val = base_stats.get(s_key, 1)
            base_stats[s_key] = current_val * 1.001
            
        print(f"LEVEL UP: {char['id']} reached {runtime['level']}! Upgraded: {', '.join(chosen_stats)}")

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
        
        self.save_game_state() # Save rebirth
        return True
        
        # Autosave every 60 ticks
        if self.tick_count % 60 == 0:
            self.save_game_state()

    def save_game_state(self):
        from idle_game.core.save_manager import SaveManager
        SaveManager.save_game(self.characters, self.active_party)

    def load_game_state(self):
        from idle_game.core.save_manager import SaveManager
        save_data = SaveManager.load_game()
        if not save_data:
            return

        # Load Party
        self.active_party = save_data.get("party", [])

        # Load Character Progress
        saved_chars = save_data.get("characters", {})
        for char in self.characters:
            char_id = char["id"]
            if char_id in saved_chars:
                item = saved_chars[char_id]
                if isinstance(item, dict) and "runtime" in item:
                    # New format: {runtime: ..., base_stats: ..., metadata: ...}
                    char["runtime"].update(item.get("runtime", {}))
                    char["base_stats"].update(item.get("base_stats", {}))
                    char["metadata"].update(item.get("metadata", {}))
                else:
                    # Legacy format: item IS the runtime dict
                    char["runtime"].update(item)
                # Recalculate max_hp based on potentially loaded level
                lvl = char["runtime"]["level"]
                char["runtime"]["max_hp"] = char["base_stats"].get("max_hp", 1000) + (lvl * 10)
        
        print(f"Loaded save data for {len(saved_chars)} characters and party of {len(self.active_party)}")

    def toggle_party_member(self, char_id: str) -> bool:
        """Toggles a character in/out of the active party. Returns True if in party."""
        changed = False
        in_party = False
        if char_id in self.active_party:
            self.active_party.remove(char_id)
            changed = True
            in_party = False
        else:
            if len(self.active_party) < 5:
                self.active_party.append(char_id)
                changed = True
                in_party = True
        
        if changed:
            self.save_game_state()
        return in_party


    def init_duel(self, char_id: str):
        """Picks a random opponent and signals the duel start if not on cooldown."""
        # Check cooldown
        if char_id in self.fight_cooldown_expiry:
            if self.tick_count < self.fight_cooldown_expiry[char_id]:
                print(f"BATTLE: {char_id} is on cooldown.")
                return
            else:
                del self.fight_cooldown_expiry[char_id]

        import random
        other_ids = [cid for cid in self.characters_map.keys() if cid != char_id]
        if not other_ids:
            return
        
        opponent_id = random.choice(other_ids)
        
        # Set Cooldown for the initiator immediately: 120s (1200 ticks)
        self.fight_cooldown_expiry[char_id] = self.tick_count + 1200
        
        self.start_duel.emit(char_id, opponent_id)

    def process_combat_win(self, char_id: str):
        """Rewards the winner of a combat with a level up."""
        char = self.characters_map.get(char_id)
        if not char:
            return
            
        self.level_up_character(char)
        
        # Set Boost: 30s (at 10 ticks/s = 300 ticks)
        self.fight_boost_expiry[char_id] = self.tick_count + 300
        
        # Set Cooldown: 120s (at 10 ticks/s = 1200 ticks)
        self.fight_cooldown_expiry[char_id] = self.tick_count + 1200

        # Reset requirement for next level
        runtime = char["runtime"]
        req_mult = runtime.get("req_multiplier", 1.0)
        import random
        runtime["next_req"] = (runtime["level"] * 30 * req_mult) * random.uniform(0.95, 1.05)
        
        print(f"COMBAT REWARD: {char_id} reached Level {runtime['level']}")
        self.save_game_state()

    def process_combat_loss(self, char_id: str):
        """Applies a 1-minute 75% EXP reduction debuff to the loser."""
        char = self.characters_map.get(char_id)
        if not char:
            return
            
        # Set Debuff: 60s (at 10 ticks/s = 600 ticks)
        self.fight_debuff_expiry[char_id] = self.tick_count + 600
        
        print(f"COMBAT PENALTY: {char_id} received a 75% EXP debuff for 60s.")
        self.save_game_state()




