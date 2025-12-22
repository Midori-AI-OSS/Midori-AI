import json
from pathlib import Path
from typing import Dict, Any

class SaveManager:
    SAVE_FILE = Path("idle_game/save.json")

    @staticmethod
    def save_game(characters: list[dict[str, Any]]):
        """Saves only the runtime state of characters."""
        save_data = {}
        for char in characters:
            save_data[char["id"]] = char.get("runtime", {})
            
        try:
            with open(SaveManager.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
            print("Game saved.")
        except Exception as e:
            print(f"Error saving game: {e}")

    @staticmethod
    def load_game(characters: list[dict[str, Any]]):
        """Updates characters list with loaded runtime data."""
        if not SaveManager.SAVE_FILE.exists():
            print("No save file found.")
            return

        try:
            with open(SaveManager.SAVE_FILE, "r", encoding="utf-8") as f:
                save_data = json.load(f)
                
            for char in characters:
                char_id = char["id"]
                if char_id in save_data:
                    char["runtime"].update(save_data[char_id])
            
            print("Game loaded.")
        except Exception as e:
            print(f"Error loading game: {e}")
