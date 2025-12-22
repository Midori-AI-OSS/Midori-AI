import sys
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import QApplication
from idle_game.core.game_state import GameState
from idle_game.gui.mainwindow import MainWindow, CharacterCard

def test_party_system():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    print("Initializing GameState...")
    state = GameState()
    state.load_characters()
    state.load_game_state()
    
    # Test 1: Party Toggling
    print("Testing Party Toggling...")
    carly_id = "carly"
    if state.toggle_party_member(carly_id):
        print("PASS: Added Carly to party.")
    else:
        print("FAIL: Could not add Carly.")
        return

    if state.active_party == [carly_id]:
        print("PASS: Active party is correct.")
    else:
        print(f"FAIL: Active party is {state.active_party}")

    # Test Max Party Size
    print("Testing Max Party Size...")
    # Add 4 more
    others = [c["id"] for c in state.characters if c["id"] != carly_id][:4]
    for oid in others:
        state.toggle_party_member(oid)
    
    if len(state.active_party) == 5:
        print("PASS: Party full (5).")
    else:
        print(f"FAIL: Party size {len(state.active_party)}")

    # Try adding 6th
    sixth = [c["id"] for c in state.characters if c["id"] not in state.active_party][0]
    if not state.toggle_party_member(sixth):
        print("PASS: Prevented 6th member.")
    else:
        print("FAIL: Allowed 6th member.")

    # Test 2: MainWindow Integration
    print("Testing MainWindow instantiation...")
    window = MainWindow(state)
    
    # Simulate clicking launch
    print("Testing Launch Party...")
    window.launch_party()
    
    open_windows = len(window.character_windows)
    print(f"Open windows: {open_windows}")
    
    if open_windows == 5:
        print("PASS: 5 Identity Windows opened.")
    else:
        print(f"FAIL: Expected 5 windows, got {open_windows}")
        
    # Test Closing
    print("Testing Window Cleanups...")
    # Remove one from party
    state.toggle_party_member(carly_id) # remove carly
    window.launch_party() # Should close carly's window
    
    if len(window.character_windows) == 4:
         print("PASS: Carly window closed.")
    else:
         print(f"FAIL: Expected 4 windows, got {len(window.character_windows)}")

if __name__ == "__main__":
    test_party_system()
