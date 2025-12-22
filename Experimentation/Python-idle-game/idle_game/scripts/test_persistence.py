import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState

def test_persistence():
    # 1. Start fresh and set some state
    gs = GameState()
    gs.load_characters()
    
    char_id = "ally"
    char = gs.characters_map[char_id]
    
    print(f"Initial state for {char_id}: Level {char['runtime']['level']}")
    
    # Modify state
    char['runtime']['level'] = 10
    gs.active_party = ["ally", "becca"]
    
    print(f"Setting {char_id} to Level 10 and setting party...")
    gs.save_game_state()
    
    # 2. Simulate restart - Create new GameState
    print("\nSimulating restart...")
    gs2 = GameState()
    gs2.load_characters()
    
    char2 = gs2.characters_map[char_id]
    print(f"Reloaded state for {char_id}: Level {char2['runtime']['level']}")
    print(f"Reloaded party: {gs2.active_party}")
    
    if char2['runtime']['level'] == 10 and gs2.active_party == ["ally", "becca"]:
        print("\nSuccess: Persistence verified!")
    else:
        print("\nFailure: Persistence failed.")

if __name__ == "__main__":
    test_persistence()
