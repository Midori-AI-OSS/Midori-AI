from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from dataclasses import is_dataclass
import importlib.util
from pathlib import Path
import re
import sys


@dataclass
class PlayerConfig:
    start_hp: float = 3000.0
    # World-space anchor for the sampled player point cloud.
    # Tune this to move the character up/down.
    x: float = 0.0
    y: float = -0.92
    # World-space standoff radius used for foes to stop before overlapping the player cloud.
    radius: float = 0.45
    # Visual HP feedback: how fast removed particles return.
    particle_heal_per_s: float = 0.12
    # How much damage reduces the particle mask. Higher = more dramatic.
    particle_damage_scale: float = 2.2


@dataclass
class SpawningConfig:
    start_spawn_rate_s: float = 3.0
    spawn_speedup_per_kill: float = 0.02
    # Spawn slightly off-screen above the top edge.
    spawn_ndc_y: float = 1.1
    spawn_x_ndc_abs: float = 0.9
    # When visible foes reaches this, newly spawned foes get HP ramp.
    visible_foe_soft_target: int = 100


@dataclass
class FoeConfig:
    start_hp: float = 100.0
    # HP ramp applied to newly spawned foes after soft target is reached.
    hp_ramp_per_s: float = 0.015
    # Movement toward player.
    move_speed: float = 0.014
    # When foe reaches bottom 20% of screen (NDC y <= -0.6), it starts attacking.
    attack_zone_ndc_y: float = -0.6
    attack_interval_s: float = 1.0
    attack_damage: float = 25.0
    radius: float = 0.075
    standoff_margin: float = 0.18
    windup_s: float = 0.35


@dataclass
class ProjectileConfig:
    fire_rate_s: float = 0.22
    speed: float = 2.5
    damage: float = 3.0
    radius: float = 0.02
    points: int = 50
    trail_len: float = 0.22
    intensity: float = 2.2


@dataclass
class RenderConfig:
    # Scale applied to foe local shapes.
    foe_shape_scale: float = 0.018
    foe_points: int = 450
    # Global point sprite tuning.
    point_size: float = 7.0
    softness: float = 7.5
    depth_fade: float = 0.08
    exposure: float = 1.0


@dataclass
class UIConfig:
    spawn_bar_height_px: int = 18
    spawn_bar_margin_px: int = 12


@dataclass
class GameConfig:
    difficulty: float = 1.0
    player: PlayerConfig = field(default_factory=PlayerConfig)
    spawning: SpawningConfig = field(default_factory=SpawningConfig)
    foe: FoeConfig = field(default_factory=FoeConfig)
    projectile: ProjectileConfig = field(default_factory=ProjectileConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    ui: UIConfig = field(default_factory=UIConfig)


CONFIG = GameConfig()


def save_current_config(path: str | Path | None = None) -> None:
    """
    Persist current CONFIG values back into `config.py` by updating dataclass defaults.
    This keeps `config.py` as the single editable source of truth.
    """
    config_path = Path(path) if path is not None else Path(__file__)
    src = config_path.read_text(encoding="utf-8")

    updates: dict[str, dict[str, str]] = {
        "PlayerConfig": {
            "start_hp": _fmt_float(CONFIG.player.start_hp),
            "x": _fmt_float(CONFIG.player.x),
            "y": _fmt_float(CONFIG.player.y),
            "radius": _fmt_float(CONFIG.player.radius),
            "particle_heal_per_s": _fmt_float(CONFIG.player.particle_heal_per_s),
            "particle_damage_scale": _fmt_float(CONFIG.player.particle_damage_scale),
        },
        "SpawningConfig": {
            "start_spawn_rate_s": _fmt_float(CONFIG.spawning.start_spawn_rate_s),
            "spawn_speedup_per_kill": _fmt_float(CONFIG.spawning.spawn_speedup_per_kill),
            "spawn_ndc_y": _fmt_float(CONFIG.spawning.spawn_ndc_y),
            "spawn_x_ndc_abs": _fmt_float(CONFIG.spawning.spawn_x_ndc_abs),
            "visible_foe_soft_target": _fmt_int(CONFIG.spawning.visible_foe_soft_target),
        },
        "FoeConfig": {
            "start_hp": _fmt_float(CONFIG.foe.start_hp),
            "hp_ramp_per_s": _fmt_float(CONFIG.foe.hp_ramp_per_s),
            "move_speed": _fmt_float(CONFIG.foe.move_speed),
            "attack_zone_ndc_y": _fmt_float(CONFIG.foe.attack_zone_ndc_y),
            "attack_interval_s": _fmt_float(CONFIG.foe.attack_interval_s),
            "attack_damage": _fmt_float(CONFIG.foe.attack_damage),
            "radius": _fmt_float(CONFIG.foe.radius),
            "standoff_margin": _fmt_float(CONFIG.foe.standoff_margin),
            "windup_s": _fmt_float(CONFIG.foe.windup_s),
        },
        "ProjectileConfig": {
            "fire_rate_s": _fmt_float(CONFIG.projectile.fire_rate_s),
            "speed": _fmt_float(CONFIG.projectile.speed),
            "damage": _fmt_float(CONFIG.projectile.damage),
            "radius": _fmt_float(CONFIG.projectile.radius),
            "points": _fmt_int(CONFIG.projectile.points),
            "trail_len": _fmt_float(CONFIG.projectile.trail_len),
            "intensity": _fmt_float(CONFIG.projectile.intensity),
        },
        "RenderConfig": {
            "foe_shape_scale": _fmt_float(CONFIG.render.foe_shape_scale),
            "foe_points": _fmt_int(CONFIG.render.foe_points),
            "point_size": _fmt_float(CONFIG.render.point_size),
            "softness": _fmt_float(CONFIG.render.softness),
            "depth_fade": _fmt_float(CONFIG.render.depth_fade),
            "exposure": _fmt_float(CONFIG.render.exposure),
        },
        "UIConfig": {
            "spawn_bar_height_px": _fmt_int(CONFIG.ui.spawn_bar_height_px),
            "spawn_bar_margin_px": _fmt_int(CONFIG.ui.spawn_bar_margin_px),
        },
        "GameConfig": {
            "difficulty": _fmt_float(CONFIG.difficulty),
        },
    }

    changed = False
    for class_name, fields in updates.items():
        src, did = _rewrite_dataclass_defaults(src, class_name=class_name, fields=fields)
        changed = changed or did

    if changed:
        config_path.write_text(src, encoding="utf-8")


def reload_config_from_disk(path: str | Path | None = None) -> None:
    """
    Reload `config.py` from disk and copy values into the existing CONFIG object.
    This lets a running app pick up edits made directly in `config.py`.
    """
    config_path = Path(path) if path is not None else Path(__file__)
    spec = importlib.util.spec_from_file_location("_pcg_config_disk", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load config module from {config_path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
    if not hasattr(module, "CONFIG"):
        raise RuntimeError(f"{config_path} did not define CONFIG")
    _copy_dataclass(module.CONFIG, CONFIG)


def _copy_dataclass(src, dst) -> None:
    if not is_dataclass(src) or not is_dataclass(dst):
        raise TypeError("reload_config_from_disk expected dataclass config objects")
    for f in fields(dst):
        name = f.name
        src_val = getattr(src, name)
        dst_val = getattr(dst, name)
        if is_dataclass(src_val) and is_dataclass(dst_val):
            _copy_dataclass(src_val, dst_val)
        else:
            setattr(dst, name, src_val)


def _fmt_float(value: float) -> str:
    return repr(float(value))


def _fmt_int(value: int) -> str:
    return str(int(value))


def _rewrite_dataclass_defaults(src: str, *, class_name: str, fields: dict[str, str]) -> tuple[str, bool]:
    block_re = re.compile(
        rf"(?ms)^@dataclass[^\n]*\nclass {re.escape(class_name)}:[\s\S]*?(?=^@dataclass|\Z)"
    )
    match = block_re.search(src)
    if match is None:
        raise ValueError(f"Could not find dataclass block for {class_name}")

    block = match.group(0)
    updated_block = block
    did_change = False

    for field_name, field_value in fields.items():
        line_re = re.compile(rf"(?m)^(\s*{re.escape(field_name)}\s*:\s*[^=\n]+?=\s*)([^#\n]+)")
        line_match = line_re.search(updated_block)
        if line_match is None:
            raise ValueError(f"Could not find field {class_name}.{field_name} in config.py")
        prefix = line_match.group(1)
        existing = line_match.group(2).strip()
        if existing == field_value.strip():
            continue
        updated_block = line_re.sub(rf"\g<1>{field_value}", updated_block, count=1)
        did_change = True

    if not did_change:
        return src, False

    out = src[: match.start()] + updated_block + src[match.end() :]
    return out, True
