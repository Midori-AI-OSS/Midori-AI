import json
from pathlib import Path
from typing import Dict, Any, List
import random
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
        
        # Risk & Reward Penalties (Stacking)
        self.rr_penalty_expiry: Dict[str, int] = {}
        self.rr_penalty_stacks: Dict[str, int] = {}
 
        self.mods = {
            "shared_exp": False,
            "risk_reward": {"enabled": False, "level": 1}
        }

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

                # Resolve Damage Type
                dtype = char.get("damage_type", "Dark")
                if dtype == "load_damage_type":
                    if char["id"] == "luna":
                        dtype = "Generic"
                    elif char["id"] == "lady_fire_and_ice":
                        dtype = "Fire / Ice"
                    elif char["id"] == "persona_light_and_dark":
                        dtype = "Light / Dark"
                    elif char["id"] == "lady_storm":
                        dtype = "Lightning / Wind"
                    else:
                        dtype = "Dark"
                char["damage_type"] = dtype

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
                    char["runtime"]["max_hp"] = char["base_stats"].get("max_hp", 1000) + (char["runtime"]["level"] * 10)
                    if char["runtime"]["hp"] > char["runtime"]["max_hp"]:
                        char["runtime"]["hp"] = char["runtime"]["max_hp"]
                
                # Snapshot the base stats after randomization but before any level-up growth
                if "initial_base_stats" not in char:
                    char["initial_base_stats"] = char["base_stats"].copy()

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

        # Calculate shared bonus once per tick if mod is active
        shared_bonus = 0.0
        if self.mods.get("shared_exp"):
            for vid in self.active_viewing_ids:
                vchar = self.characters_map.get(vid)
                if vchar:
                    v_rt = vchar["runtime"]
                    v_exp_mult = v_rt.get("exp_multiplier", 1.0)
                    v_c_mult = 1.0
                    if vchar["id"] in self.fight_boost_expiry and self.tick_count < self.fight_boost_expiry[vchar["id"]]:
                        v_c_mult = 2.0
                    elif vchar["id"] in self.fight_debuff_expiry and self.tick_count < self.fight_debuff_expiry[vchar["id"]]:
                        v_c_mult = 0.25
                    
                    # 1% of untaxed potential
                    shared_bonus += (1.0 * v_exp_mult * v_c_mult) * 0.01

        needs_save = False
        for char_id, char in self.characters_map.items():
            runtime = char["runtime"]
            exp_mult = runtime.get("exp_multiplier", 1.0)
            req_mult = runtime.get("req_multiplier", 1.0)
            
            # Fight Boost/Debuff Logic
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

            # 1. Calculate Base Gain
            raw_gain = 1 * exp_mult * combat_mult
            
            # --- Apply Stacking Death Penalties ---
            stacks = self.rr_penalty_stacks.get(char_id, 0)
            if stacks > 0 and char_id in self.rr_penalty_expiry:
                if self.tick_count < self.rr_penalty_expiry[char_id]:
                    penalty_mult = 0.01 ** stacks
                    raw_gain *= penalty_mult
                else:
                    del self.rr_penalty_expiry[char_id]
                    self.rr_penalty_stacks[char_id] = 0

            # 2. View-based constraint & Mod tax
            is_viewed = char["id"] in self.active_viewing_ids
            gain = raw_gain
            
            if self.mods.get("shared_exp"):
                if is_viewed:
                    gain *= 0.45 
                else:
                    gain = 0 
            else:
                if not is_viewed:
                    gain = 0 

            # Risk & Reward Mod: Multiplier
            rr = self.mods.get("risk_reward", {})
            if rr.get("enabled"):
                gain *= (rr.get("level", 1) + 1)

            # 3. Apply gain + global shared bonus
            runtime["exp"] += gain + shared_bonus

            # --- Regeneration & Risk/Reward Damage ---
            eff = self.get_effective_stats(char)
            regain = eff.get("regain", 0)
            if "Light" in char.get("damage_type", ""):
                 regain *= 15.0
            
            # Apply passive regain
            regain_tick = regain / 10.0
            if not self.active_viewing_ids:
                regain_tick += 5.0 # Everyone gets 5 HP/tick bonus when idle (no windows)
            
            runtime["hp"] = min(runtime["max_hp"], runtime["hp"] + regain_tick)

            # Risk & Reward Penalty: ONLY for characters who are currently obtaining bonus (viewed)
            # This prevents killing the entire roster in the background.
            if rr.get("enabled") and is_viewed and self.tick_count % 5 == 0:
                drain = 1.5 * rr.get("level", 1)
                prev_hp = runtime["hp"]
                runtime["hp"] -= drain
                
                # Handling "Death" - Only trigger if they were above 0
                if runtime["hp"] <= 0 and prev_hp > 0:
                    runtime["hp"] = 0
                    penalty_ticks = 35 * 60 * 10
                    self.rr_penalty_stacks[char_id] = self.rr_penalty_stacks.get(char_id, 0) + 1
                    
                    current_expiry = self.rr_penalty_expiry.get(char_id, self.tick_count)
                    base_time = max(self.tick_count, current_expiry)
                    self.rr_penalty_expiry[char_id] = base_time + penalty_ticks
                    needs_save = True

            # Level Up Logic
            if "next_req" not in runtime:
                runtime["next_req"] = (runtime["level"] * 30 * req_mult) * random.uniform(0.95, 1.05)
            
            if runtime["exp"] >= runtime["next_req"]:
                self.level_up_character(char)
                
                # Dynamic Slowdown: Compounding 1.5x tax per 5 levels over 50
                lvl = runtime["level"]
                tax_mult = 1.0
                if lvl >= 50:
                    steps = (lvl - 50) // 5
                    tax_mult = (1.5 ** steps)
                
                runtime["next_req"] = (lvl * 30 * req_mult * tax_mult) * random.uniform(0.95, 1.05)
                needs_save = True

        # Global Save Logic
        if needs_save or (self.tick_count % 125 == 0):
            self.save_game_state()

    def level_up_character(self, char: Dict[str, Any]):
        """Increments level and applies weighted stat upgrades."""
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
            w = 0.1
            # Scaling factors to make smaller stats relevant
            if key in ["crit_rate", "dodge_odds", "mitigation"]: # Usually small values
                w = val * 100
            elif key == "crit_damage": # 1.5 -> 15
                w = val * 10
            else:
                w = val
            
            # Character specific favors
            if char["id"] == "luna" and key == "dodge_odds":
                w *= 5 # Luna favors dodge significantly
                
            weights.append(w)
        
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
        
        # Capture old level for bonus calculation
        old_level = runtime["level"]
        
        # Reset Stats
        runtime["level"] = 1
        runtime["exp"] = 0
        
        # RESTORE BASE STATS to their initial level 1 values (wiping level-up growth)
        if "initial_base_stats" in char:
            char["base_stats"] = char["initial_base_stats"].copy()
            
        runtime["max_hp"] = char["base_stats"].get("max_hp", 1000)
        runtime["hp"] = runtime["max_hp"]
        
        # Apply Bonuses
        # Formula: 0.25 * (1 + 0.01 * (old_level - 50))
        bonus = 0.25 * (1 + 0.01 * (old_level - 50))
        
        current_exp_mult = runtime.get("exp_multiplier", 1.0)
        runtime["exp_multiplier"] = current_exp_mult + bonus
        
        # Apply EXP Tax (Permanent 5% per Rebirth)
        current_req_mult = runtime.get("req_multiplier", 1.0)
        runtime["req_multiplier"] = current_req_mult + 0.05
        
        # Track Rebirths
        runtime["rebirths"] = runtime.get("rebirths", 0) + 1
        
        # Reset EXP requirement for Level 1
        req_mult = runtime["req_multiplier"]
        runtime["next_req"] = (1 * 30 * req_mult) * random.uniform(0.95, 1.05)
        
        self.save_game_state() # Save rebirth
        return True
        
        # Autosave every 60 ticks
        if self.tick_count % 60 == 0:
            self.save_game_state()

    def save_game_state(self):
        from idle_game.core.save_manager import SaveManager
        SaveManager.save_game(self.characters, self.active_party)
        SaveManager.save_setting("active_mods", self.mods)
        SaveManager.save_setting("rr_penalty_expiry", self.rr_penalty_expiry)
        SaveManager.save_setting("rr_penalty_stacks", self.rr_penalty_stacks)

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
                    # New format: {runtime: ..., base_stats: ..., metadata: ..., initial_base_stats: ...}
                    char["runtime"].update(item.get("runtime", {}))
                    char["base_stats"].update(item.get("base_stats", {}))
                    if "initial_base_stats" in item:
                        char["initial_base_stats"] = item["initial_base_stats"].copy()
                    char["metadata"].update(item.get("metadata", {}))
                else:
                    # Legacy format: item IS the runtime dict
                    char["runtime"].update(item)
                # Recalculate max_hp based on potentially loaded level
                lvl = char["runtime"]["level"]
                char["runtime"]["max_hp"] = char["base_stats"].get("max_hp", 1000) + (lvl * 10)
        
        saved_mods = SaveManager.load_setting("active_mods")
        if saved_mods:
            self.mods.update(saved_mods)
            
        self.rr_penalty_expiry = SaveManager.load_setting("rr_penalty_expiry", {})
        self.rr_penalty_stacks = SaveManager.load_setting("rr_penalty_stacks", {})
            
        print(f"Loaded save data for {len(saved_chars)} characters and party of {len(self.active_party)}")

    TYPE_CHART = {
        "Fire": {"weakness": "Ice", "resistance": "Fire", "color": "#e74c3c"},
        "Ice": {"weakness": "Fire", "resistance": "Ice", "color": "#3498db"},
        "Wind": {"weakness": "Lightning", "resistance": "Wind", "color": "#2ecc71"},
        "Lightning": {"weakness": "Wind", "resistance": "Lightning", "color": "#f1c40f"},
        "Light": {"weakness": "Dark", "resistance": "Light", "color": "#ecf0f1"},
        "Dark": {"weakness": "Light", "resistance": "Dark", "color": "#9b59b6"},
        "Generic": {"weakness": "none", "resistance": "all", "color": "#bdc3c7"}
    }

    def get_type_multiplier(self, attacker_type: str, defender_type: str) -> float:
        """Calculates damage multiplier based on elemental typing."""
        if not attacker_type or not defender_type:
            return 1.0
            
        def_info = self.TYPE_CHART.get(defender_type, self.TYPE_CHART["Generic"])
        
        # Weakness: Attacker is what Defender is weak against
        if def_info["weakness"] == attacker_type:
            return 1.25
            
        # Resistance: Attacker is what Defender resists
        if def_info["resistance"] == "all" or def_info["resistance"] == attacker_type:
            return 0.75
            
        return 1.0

    def get_effective_stats(self, char_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates derived stats based on base stats, level, and rebirths."""
        runtime = char_data["runtime"]
        base_stats = char_data["base_stats"]
        level = runtime["level"]
        rebirths = runtime.get("rebirths", 0)
        
        # Base stats (including level-up specializations)
        stats = base_stats.copy()
        
        # Consistent ATK & DEF formulas
        stats["atk"] = stats.get("atk", 10) + (level * 2)
        stats["defense"] = stats.get("defense", 0) + (level * 1)
        
        # Dodge Growth: +0.01 per 25 levels (x2+rebirths) with fall-off at 50
        dodge_lvl = min(level, 50)
        if level > 50:
            dodge_lvl += (level - 50) ** 0.5 # Logarithmic fall-off after 50
        
        dodge_bonus = (dodge_lvl / 25.0) * 0.01 * (2 + rebirths)
        stats["dodge_odds"] = stats.get("dodge_odds", 0) + dodge_bonus
        
        # Regain Growth: +0.2 per tick per 50 levels (x5 times rebirths)
        # Note: 5*rebirths means 0 if no rebirths, as per literal request
        regen_bonus = (level / 50.0) * 0.2 * (5 * rebirths)
        stats["regain"] = stats.get("regain", 0) + regen_bonus
        
        return stats


    def init_duel(self, char_id: str):
        """Picks a random opponent and signals the duel start if not on cooldown."""
        # Check cooldown
        if char_id in self.fight_cooldown_expiry:
            if self.tick_count < self.fight_cooldown_expiry[char_id]:
                print(f"BATTLE: {char_id} is on cooldown.")
                return
            else:
                del self.fight_cooldown_expiry[char_id]

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




