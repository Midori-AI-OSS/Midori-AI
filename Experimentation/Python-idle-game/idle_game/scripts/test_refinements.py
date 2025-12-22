import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import QApplication
from idle_game.core.game_state import GameState
from idle_game.gui.character_window import CharacterWindow

def test_refinements():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    print("Initializing GameState...")
    state = GameState()
    # Force reload to test randomization
    state.load_characters()
    
    char_id = "carly"
    char = state.characters_map[char_id]
    
    # 1. Test Stat Randomness
    print("\n--- Testing Stat Randomness ---")
    base_atk = 100 # Standard default
    actual_atk = char["base_stats"]["atk"]
    print(f"Base ATK: {base_atk}, Actual Randomized ATK: {actual_atk}")
    if actual_atk >= 90 and actual_atk <= 110:
        if actual_atk != 100:
             print("PASS: ATK is randomized within +/- 10%.")
        else:
             print("WARN: ATK is exactly 100 (could be luck, running again might differ).") 
    else:
        print("FAIL: ATK variance out of bounds.")
        
    # 2. Test Conditional EXP
    print("\n--- Testing Conditional EXP ---")
    runtime = char["runtime"]
    runtime["exp"] = 0
    state.active_viewing_ids.clear()
    
    # Tick with NO viewing
    state._on_tick()
    if runtime["exp"] == 0:
        print("PASS: No EXP gained when not viewing.")
    else:
        print(f"FAIL: Gained {runtime['exp']} EXP despite closed window.")
        
    # Tick WITH viewing
    state.start_viewing(char_id)
    state._on_tick()
    if runtime["exp"] > 0:
        print("PASS: EXP gained when viewing.")
    else:
        print(f"FAIL: No EXP gained when viewing.")
        
    # 3. Test UI / Stats text
    print("\n--- Testing UI Stats ---")
    window = CharacterWindow(char, state)
    window.update_stats(0)
    
    text = window.extra_stats_label.text()
    print(f"Stats Text: {text}")
    if "Crit Rate" in text and "Dodge" in text:
        print("PASS: Extra stats displayed.")
    else:
        print("FAIL: Extra stats missing from label.")

if __name__ == "__main__":
    test_refinements()
