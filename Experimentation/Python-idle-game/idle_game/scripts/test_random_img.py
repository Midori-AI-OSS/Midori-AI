import sys
from pathlib import Path
# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState
import os

def test_random_image():
    gs = GameState()
    # Mock data path if needed? No, GameState uses its own relative path
    gs.load_characters()
    
    luna = gs.characters_map.get("luna")
    if not luna:
        print("Luna not found in characters!")
        return
        
    portrait = luna.get("ui", {}).get("portrait")
    print(f"Initial load portrait for Luna: {portrait}")
    
    # Reload and see if it changes (luck based, but at least verify it's a file now)
    gs2 = GameState()
    gs2.load_characters()
    luna2 = gs2.characters_map.get("luna")
    portrait2 = luna2.get("ui", {}).get("portrait")
    print(f"Second load portrait for Luna: {portrait2}")
    
    if portrait and Path(portrait).is_file():
        print("Success: Portrait is a file.")
    else:
        print("Failure: Portrait is not a file.")

if __name__ == "__main__":
    test_random_image()
