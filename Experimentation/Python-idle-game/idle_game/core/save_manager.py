import json
from pathlib import Path
from typing import Dict, Any

class SaveManager:
    SAVE_FILE = Path(__file__).parent.parent / "data" / "save.json"

    @staticmethod
    def save_game(characters: list[dict[str, Any]], party: list[str]):
        """Saves character runtime stats and the active party."""
        save_data = {
            "characters": {},
            "party": party
        }
        for char in characters:
            save_data["characters"][char["id"]] = {
                "runtime": char.get("runtime", {}),
                "base_stats": char.get("base_stats", {}),
                "metadata": char.get("metadata", {})
            }
            
        try:
            # Ensure data dir exists
            SaveManager.SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SaveManager.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
            print(f"Game saved to {SaveManager.SAVE_FILE}")
        except Exception as e:
            print(f"Error saving game: {e}")

    @staticmethod
    def load_game():
        """Loads and returns the saved game data dictionary."""
        if not SaveManager.SAVE_FILE.exists():
            return None

        try:
            with open(SaveManager.SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading game: {e}")
            return None

