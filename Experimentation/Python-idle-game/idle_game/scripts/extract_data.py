import ast
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import shutil

# Constants
PLUGIN_DIR = Path("/tmp/Midori-AI-AutoFighter/backend/plugins/characters")
OUTPUT_FILE = Path("idle_game/data/characters.json")
# ASSET source still needs to be capable of handling the temp dir if we re-cloned? 
# The user said "Clone down... to a tmp folder". 
# So assets are now at /tmp/Midori-AI-AutoFighter/frontend/src/lib/assets/characters
ASSET_BASE_DIR = Path("/tmp/Midori-AI-AutoFighter/frontend/src/lib/assets/characters")
LOCAL_ASSET_DIR = Path("idle_game/assets/characters")

@dataclass
class CharacterData:
    id: str
    name: str = ""
    short_lore: str = ""
    full_lore: str = ""
    char_type: str = "C"
    gacha_rarity: int = 0
    damage_type: str = "Physical"
    passives: List[str] = field(default_factory=list)
    special_abilities: List[str] = field(default_factory=list)
    ui: Dict[str, Any] = field(default_factory=dict)
    base_stats: Dict[str, Any] = field(default_factory=lambda: {
        "max_hp": 1000,
        "atk": 100,
        "defense": 50,
        "mitigation": 1.0,
        "base_aggro": 1.0,
        "crit_rate": 0.05,
        "crit_damage": 2.0,
        "effect_hit_rate": 1.0,
        "regain": 0,
        "dodge_odds": 0.0,
        "effect_resistance": 0.0,
        "vitality": 1.0
    })
    growth: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

def parse_python_file(file_path: Path) -> Optional[CharacterData]:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        print(f"Error parsing {file_path}")
        return None

    char_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            char_class = node
            break

    if not char_class:
        return None

    data = CharacterData(id="")
    
    # helper to unquote strings
    def get_value(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.List):
            return [get_value(el) for el in node.elts]
        elif isinstance(node, ast.Dict):
             return {get_value(k): get_value(v) for k, v in zip(node.keys, node.values)}
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
             for kw in node.keywords:
                 if kw.arg == 'default_factory':
                     if isinstance(kw.value, ast.Lambda):
                         return get_value(kw.value.body)
                     elif isinstance(kw.value, ast.Name):
                         return kw.value.id
             for kw in node.keywords:
                if kw.arg == 'default':
                    return get_value(kw.value)
             if isinstance(node.func, ast.Name):
                 return node.func.id

        return None

    # Parse class attributes
    for node in char_class.body:
        if isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            target_name = targets[0].id if isinstance(targets[0], ast.Name) else None
            
            if not target_name:
                continue

            value = node.value if isinstance(node, ast.Assign) else node.value
            if not value:
                continue

            val = get_value(value)

            if target_name == "id":
                data.id = val
            elif target_name == "name":
                data.name = val
            elif target_name == "summarized_about":
                data.short_lore = val
            elif target_name == "full_about":
                data.full_lore = val
            elif target_name == "char_type":
                data.char_type = val
            elif target_name == "gacha_rarity":
                data.gacha_rarity = val
            elif target_name == "damage_type":
                data.damage_type = str(val)
            elif target_name == "passives":
                data.passives = val
            elif target_name == "special_abilities":
                data.special_abilities = val
            elif target_name == "actions_display":
                data.ui["actions_display"] = val
            elif target_name == "stat_gain_map":
                data.growth["stat_gain_map"] = val
            elif target_name == "ui_portrait_pool":
                data.ui["portrait_pool"] = val
            elif target_name == "ui_non_selectable":
                data.ui["non_selectable"] = val

    # Parse __post_init__ for base_stat overrides
    for node in char_class.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__post_init__":
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    if isinstance(func, ast.Attribute) and func.attr == "set_base_stat":
                        args = stmt.value.args
                        if len(args) >= 2:
                            key = get_value(args[0])
                            val = get_value(args[1])
                            if key and val is not None:
                                data.base_stats[key] = val
                
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                            key = target.attr
                            val = get_value(stmt.value)
                            
                            # Normalize key (strip _base_ prefix if present, though PlayerBase uses it, subclasses might too)
                            clean_key = key.replace("_base_", "")
                            if clean_key == "hp": clean_key = "max_hp" # often aliased

                            accepted_stats = [
                                "base_aggro", "max_hp", "atk", "defense", "mitigation",
                                "crit_rate", "crit_damage", "effect_hit_rate", "regain", 
                                "dodge_odds", "effect_resistance", "vitality"
                            ]

                            if clean_key in accepted_stats:
                                if isinstance(val, (int, float)):
                                    data.base_stats[clean_key] = val
                            
                            if key == "damage_reduction_passes":
                                    data.metadata["damage_reduction_passes"] = val

    
    if not data.id:
        return None

    # Derive asset path and COPY asset
    potential_path = ASSET_BASE_DIR / f"{data.id}.png"
    destination_path = LOCAL_ASSET_DIR / f"{data.id}.png"
    
    # Ensure local asset dir exists
    LOCAL_ASSET_DIR.mkdir(parents=True, exist_ok=True)

    if potential_path.exists():
        try:
            shutil.copy2(potential_path, destination_path)
            # Store RELATIVE path for portable usage (assuming running from project root)
            data.ui["portrait"] = str(destination_path)
        except Exception as e:
            print(f"Failed to copy asset {potential_path}: {e}")
            data.ui["portrait"] = None
    else:
        # Check folder (skip complex folder logic for now, just look for main png)
        # or maybe we can copy the folder? simplified for now as per MVP
        data.ui["portrait"] = None


    return data

def main():
    characters = []
    
    # Ensure raw output dir
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    for file_path in PLUGIN_DIR.glob("*.py"):
        if file_path.name.startswith("_") or file_path.name == "slime.py" or file_path.name == "foe_base.py":
            continue
            
        print(f"Processing {file_path.name}...")
        char_data = parse_python_file(file_path)
        if char_data:
            characters.append(asdict(char_data))
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(characters, f, indent=2)
    
    print(f"Extracted {len(characters)} characters to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
