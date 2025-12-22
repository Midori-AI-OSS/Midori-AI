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
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
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
    # Strategy: 
    # 1. Exact match in ASSET_BASE_DIR/{id}.png
    # 2. Check for folder match ASSET_BASE_DIR/{id} or ASSET_BASE_DIR/{id without prefix}
    # 3. If folder found, COPY THE ENTIRE FOLDER to LOCAL_ASSET_DIR/{id}/
    # 4. If only file found, copy to LOCAL_ASSET_DIR/{id}.png
    
    source_path = None
    is_directory = False
    
    # 1. Direct match (File)
    direct_path = ASSET_BASE_DIR / f"{data.id}.png"
    if direct_path.exists():
        source_path = direct_path
        is_directory = False
    
    # 2. Folder match (Preferred over single file if we want random images?)
    # Actually, if a folder exists, it usually contains variations.
    # Let's check for folder first or second? 
    # Existing behavior: checking file first.
    # Let's check for folder.
    
    folder_candidates = [
        ASSET_BASE_DIR / data.id,
    ]
    if data.id.startswith("lady_"):
        folder_candidates.append(ASSET_BASE_DIR / data.id.replace("lady_", ""))
    
    found_folder = None
    for cand in folder_candidates:
        if cand.exists() and cand.is_dir():
            found_folder = cand
            break
            
    if found_folder:
        source_path = found_folder
        is_directory = True
    elif not source_path:
        # If no folder and no direct file matched yet, check fuzzy file locations?
        pass

    # Destination
    if is_directory and source_path:
        dest_dir = LOCAL_ASSET_DIR / data.id
        if dest_dir.exists():
            shutil.rmtree(dest_dir) # Clean replace
        try:
            shutil.copytree(source_path, dest_dir)
            data.ui["portrait"] = str(dest_dir)
            print(f"  Copied image directory for {data.id} from {source_path}")
        except Exception as e:
            print(f"Failed to copy directory {source_path}: {e}")
            data.ui["portrait"] = None
            
    elif source_path and not is_directory:
        dest_file = LOCAL_ASSET_DIR / f"{data.id}.png"
        LOCAL_ASSET_DIR.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, dest_file)
            data.ui["portrait"] = str(dest_file)
            print(f"  Copied image file for {data.id} from {source_path}")
        except Exception as e:
             print(f"Failed to copy file {source_path}: {e}")
             data.ui["portrait"] = None
    else:
        print(f"  No image found for {data.id}")
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
