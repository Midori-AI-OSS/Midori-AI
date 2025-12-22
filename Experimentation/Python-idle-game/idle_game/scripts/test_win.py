import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState

def test_win_reward():
    gs = GameState()
    gs.load_characters()
    
    char_id = "becca"
    char = gs.characters_map[char_id]
    initial_lvl = char["runtime"]["level"]
    print(f"Initial level for {char_id}: {initial_lvl}")
    
    print(f"Processing win for {char_id}...")
    gs.process_combat_win(char_id)
    
    # Reload and check
    gs2 = GameState()
    gs2.load_characters()
    reloaded_lvl = gs2.characters_map[char_id]["runtime"]["level"]
    print(f"Reloaded level for {char_id}: {reloaded_lvl}")
    
    if reloaded_lvl == initial_lvl + 1:
        print("Success: Level up persisted!")
    else:
        print("Failure: Level up did not persist.")

if __name__ == "__main__":
    test_win_reward()
