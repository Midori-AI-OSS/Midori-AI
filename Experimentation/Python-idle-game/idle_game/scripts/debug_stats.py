import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState

def test_stat_independence():
    state = GameState()
    state.load_characters()
    
    # Get two characters
    c1 = state.characters[0] # Ally
    c2 = state.characters[1] # Becca
    
    print(f"Char 1: {c1['id']} - EXP: {c1['runtime']['exp']}")
    print(f"Char 2: {c2['id']} - EXP: {c2['runtime']['exp']}")
    
    # Modify Char 1 ONLY
    print("Modifying Char 1 EXP to 50...")
    c1['runtime']['exp'] = 50
    
    print(f"Char 1: {c1['id']} - EXP: {c1['runtime']['exp']}")
    print(f"Char 2: {c2['id']} - EXP: {c2['runtime']['exp']}")
    
    if c2['runtime']['exp'] == 50:
        print("FAIL: Char 2 was modified! Data is linked.")
    else:
        print("PASS: Char 2 was not modified. Data is independent.")

if __name__ == "__main__":
    test_stat_independence()
