import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState

def test_duel_init():
    gs = GameState()
    gs.load_characters()
    
    char_id = "ally"
    print(f"Initializing duel for {char_id}...")
    
    def on_start_duel(c1, c2):
        print(f"Duel Started: {c1} vs {c2}")
        if c1 == char_id and c2 != char_id:
            print("Success: Valid duel signaled.")
        else:
            print("Failure: Invalid duel partners.")

    gs.start_duel.connect(on_start_duel)
    gs.init_duel(char_id)

if __name__ == "__main__":
    test_duel_init()
