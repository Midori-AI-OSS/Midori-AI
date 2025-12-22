import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from idle_game.gui.mainwindow import MainWindow
from idle_game.core.game_state import GameState

def main():
    app = QApplication(sys.argv)
    
    # Initialize Game Logic
    game_state = GameState()
    game_state.load_characters()
    game_state.load_game_state()
    
    # Initialize Main Window
    window = MainWindow(game_state)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
