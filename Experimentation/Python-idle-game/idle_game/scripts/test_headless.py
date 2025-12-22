import sys
from pathlib import Path
import time

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from idle_game.core.game_state import GameState
from idle_game.core.save_manager import SaveManager

def test_headless():
    print("Initializing GameState...")
    state = GameState()
    state.load_characters()
    
    # Test character loading
    if not state.characters:
        print("FAIL: No characters loaded.")
        return
    print(f"PASS: Loaded {len(state.characters)} characters.")
    
    # Check initial state of a character (e.g., Carly)
    carly = state.characters_map.get("carly")
    if not carly:
        print("FAIL: Carly not found.")
        return
    
    print(f"Carly initial level: {carly['runtime']['level']}")
    
    # Simulate ticks
    print("Simulating 110 ticks (should trigger level up due to 100 exp threshold)...")
    for _ in range(110):
        state._on_tick()
        
    print(f"Carly level after ticks: {carly['runtime']['level']}")
    if carly['runtime']['level'] > 1:
        print("PASS: Level up logic working.")
    else:
        print("FAIL: Level up logic failed.")

    # Test Save
    print("Testing Save...")
    state.save_game_state()
    if SaveManager.SAVE_FILE.exists():
        print("PASS: Save file created.")
    else:
        print("FAIL: Save file not created.")

    # Test Load
    print("Testing Load...")
    # Create new state to simulate restart
    new_state = GameState()
    new_state.load_characters()
    new_state.load_game_state()
    
    new_carly = new_state.characters_map.get("carly")
    if new_carly['runtime']['level'] == carly['runtime']['level']:
        print("PASS: Data persistence verified.")
    else:
        print(f"FAIL: Data persistence failed. Expected {carly['runtime']['level']}, got {new_carly['runtime']['level']}")

if __name__ == "__main__":
    test_headless()
