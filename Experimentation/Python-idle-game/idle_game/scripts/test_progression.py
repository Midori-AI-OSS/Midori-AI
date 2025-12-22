import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from idle_game.core.game_state import GameState

def test_progression():
    gs = GameState()
    gs.load_characters()
    
    char_id = "ally"
    char = gs.characters_map[char_id]
    
    print(f"Starting Level UP simulation for {char_id}...")
    initial_atk = char["base_stats"]["atk"]
    initial_mit = char["base_stats"].get("mitigation", 0)
    
    # Simulate 50 level ups
    for i in range(50):
        gs.level_up_character(char)
        
    final_atk = char["base_stats"]["atk"]
    final_mit = char["base_stats"].get("mitigation", 0)
    
    print(f"\nFinal State after 50 Levels:")
    print(f"Level: {char['runtime']['level']}")
    print(f"ATK: {initial_atk:.2f} -> {final_atk:.2f} (Gain: {final_atk-initial_atk:.2f})")
    print(f"Mitigation: {initial_mit:.4f} -> {final_mit:.4f} (Gain: {final_mit-initial_mit:.4f})")
    
    # Check if we have multi-point logic impact
    # At high levels, we should see more upgrades per level
    expected_points = sum(1 + (lv // 10) for lv in range(2, 52))
    print(f"Total Upgrade Points Applied: ~{expected_points}")

if __name__ == "__main__":
    test_progression()
