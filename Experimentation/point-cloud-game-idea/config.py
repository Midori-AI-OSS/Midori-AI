from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerConfig:
    start_hp: float = 3000.0
    # World-space anchor for the sampled player point cloud.
    # Tune this to move the character up/down.
    x: float = 0.0
    y: float = -0.92


@dataclass(frozen=True)
class SpawningConfig:
    start_spawn_rate_s: float = 3.0
    spawn_speedup_per_kill: float = 0.02
    # Spawn slightly off-screen above the top edge.
    spawn_ndc_y: float = 1.10
    spawn_x_ndc_abs: float = 0.90
    # When visible foes reaches this, newly spawned foes get HP ramp.
    visible_foe_soft_target: int = 100


@dataclass(frozen=True)
class FoeConfig:
    start_hp: float = 100.0
    # HP ramp applied to newly spawned foes after soft target is reached.
    hp_ramp_per_s: float = 0.015
    # Movement toward player.
    move_speed: float = 0.55
    # When foe reaches bottom 20% of screen (NDC y <= -0.6), it starts attacking.
    attack_zone_ndc_y: float = -0.60
    attack_interval_s: float = 1.0
    attack_damage: float = 25.0
    radius: float = 0.5


@dataclass(frozen=True)
class ProjectileConfig:
    fire_rate_s: float = 0.25
    speed: float = 2.5
    damage: float = 10.0
    radius: float = 0.08
    points: int = 50


@dataclass(frozen=True)
class RenderConfig:
    # Scale applied to foe local shapes.
    foe_shape_scale: float = 0.20
    foe_points: int = 450


@dataclass(frozen=True)
class UIConfig:
    spawn_bar_height_px: int = 18
    spawn_bar_margin_px: int = 12


@dataclass(frozen=True)
class GameConfig:
    difficulty: float = 1.0
    player: PlayerConfig = PlayerConfig()
    spawning: SpawningConfig = SpawningConfig()
    foe: FoeConfig = FoeConfig()
    projectile: ProjectileConfig = ProjectileConfig()
    render: RenderConfig = RenderConfig()
    ui: UIConfig = UIConfig()


CONFIG = GameConfig()

