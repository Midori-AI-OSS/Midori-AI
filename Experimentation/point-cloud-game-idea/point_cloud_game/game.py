from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
import torch

from config import CONFIG
from point_cloud_game.sim_adapter import PointCloudManager


@dataclass
class Foe:
    id: int
    pool_idx: tuple[int, int]
    pos: list[float]
    hp: float
    max_hp: float
    local_shape: torch.Tensor
    radius: float = 0.5
    attacking: bool = False
    attack_timer: float = 0.0


@dataclass
class Projectile:
    id: int
    pool_idx: tuple[int, int]
    pos: list[float]
    vel: list[float]
    damage: float
    active: bool
    radius: float = 0.08


class Game:
    def __init__(self, manager: PointCloudManager, weave_image_path: str):
        self.manager = manager

        self.difficulty = float(CONFIG.difficulty)

        self.player_max_hp = float(CONFIG.player.start_hp)
        self.player_hp = float(self.player_max_hp)
        self.is_game_over = False
        self.paused = False

        self.player_pos = [float(CONFIG.player.x), float(CONFIG.player.y)]

        self.run_time_s = 0.0
        self._hp_ramp_started_at_s: float | None = None

        self.spawn_timer = 0.0
        self.spawn_rate = float(CONFIG.spawning.start_spawn_rate_s)
        self.spawn_speedup_per_kill = float(CONFIG.spawning.spawn_speedup_per_kill)
        self.hp_ramp_per_s = float(CONFIG.foe.hp_ramp_per_s)

        self.fire_timer = 0.0
        self.fire_rate = float(CONFIG.projectile.fire_rate_s)

        self.foe_attack_interval_s = float(CONFIG.foe.attack_interval_s)
        self.foe_attack_damage = float(CONFIG.foe.attack_damage)
        self._attack_ndc_y = float(CONFIG.foe.attack_zone_ndc_y)

        self.next_foe_id = 1
        self.next_projectile_id = 1

        self.foes: list[Foe] = []
        self.projectiles: list[Projectile] = []

        self._camera = None
        self._aspect: float | None = None

        self.manager.initialize_sim(weave_image_path, player_anchor=(self.player_pos[0], self.player_pos[1], 0.0))
        self.reset()

    def set_view(self, *, camera, aspect: float) -> None:
        self._camera = camera
        self._aspect = float(aspect)

    def reset(self) -> None:
        for foe in self.foes:
            self._hide_foe(foe)
            self.manager.free_foe(foe.pool_idx)
        for proj in self.projectiles:
            self._hide_projectile(proj)

        self.foes.clear()
        self.projectiles.clear()
        self.manager.reset_dynamic_allocators()

        self.player_hp = float(self.player_max_hp)
        self.is_game_over = False
        self.paused = True
        self.run_time_s = 0.0
        self._hp_ramp_started_at_s = None

        self.spawn_timer = 0.0
        self.spawn_rate = float(CONFIG.spawning.start_spawn_rate_s)
        self.fire_timer = 0.0
        self.spawn_timer = float(self.spawn_rate)

    def update(self, dt: float) -> None:
        if self.paused or self.is_game_over:
            return

        self.run_time_s += float(dt)

        visible = self._visible_foe_count()
        if visible >= int(CONFIG.spawning.visible_foe_soft_target) and self._hp_ramp_started_at_s is None:
            self._hp_ramp_started_at_s = float(self.run_time_s)

        self.spawn_timer -= float(dt)
        while self.spawn_timer <= 0.0:
            self._spawn_foe()
            self.spawn_timer += float(self.spawn_rate)

        self._update_foes(float(dt))
        kills = self._update_projectiles(float(dt))
        if kills > 0:
            for _ in range(kills):
                self.spawn_rate *= float(1.0 - self.spawn_speedup_per_kill)

        self._auto_fire(float(dt))
        self._sync_sim()

    def _world_to_ndc(self, x: float, y: float, z: float) -> np.ndarray | None:
        if self._camera is None or self._aspect is None:
            return None
        view = self._camera.view_matrix()
        proj = self._camera.proj_matrix(float(self._aspect))
        v = np.array([float(x), float(y), float(z), 1.0], dtype=np.float32)
        clip = (proj @ view) @ v
        w = float(clip[3])
        if abs(w) < 1e-6:
            return None
        return clip[:3] / w

    def _ndc_to_world_z0(self, nx: float, ny: float) -> np.ndarray | None:
        if self._camera is None or self._aspect is None:
            return None
        view = self._camera.view_matrix()
        proj = self._camera.proj_matrix(float(self._aspect))
        inv = np.linalg.inv(proj @ view).astype(np.float32)

        near = np.array([float(nx), float(ny), -1.0, 1.0], dtype=np.float32)
        far = np.array([float(nx), float(ny), 1.0, 1.0], dtype=np.float32)
        w_near = inv @ near
        w_far = inv @ far
        if abs(float(w_near[3])) < 1e-6 or abs(float(w_far[3])) < 1e-6:
            return None

        p0 = w_near[:3] / w_near[3]
        p1 = w_far[:3] / w_far[3]
        d = p1 - p0
        dz = float(d[2])
        if abs(dz) < 1e-6:
            return None
        t = -float(p0[2]) / dz
        return p0 + d * t

    def _visible_foe_count(self) -> int:
        count = 0
        for foe in self.foes:
            ndc = self._world_to_ndc(foe.pos[0], foe.pos[1], 0.0)
            if ndc is None:
                continue
            if abs(float(ndc[0])) <= 1.0 and abs(float(ndc[1])) <= 1.0:
                count += 1
        return count

    def _in_attack_zone(self, foe: Foe) -> bool:
        ndc = self._world_to_ndc(foe.pos[0], foe.pos[1], 0.0)
        if ndc is None:
            return False
        return float(ndc[1]) <= float(self._attack_ndc_y)

    def _spawn_foe(self) -> None:
        pts = int(CONFIG.render.foe_points)
        indices = self.manager.allocate_foe(pts)
        if indices is None:
            return

        if self._camera is not None and self._aspect is not None:
            nx = random.uniform(-float(CONFIG.spawning.spawn_x_ndc_abs), float(CONFIG.spawning.spawn_x_ndc_abs))
            ny = float(CONFIG.spawning.spawn_ndc_y)
            world = self._ndc_to_world_z0(nx, ny)
            if world is not None:
                x = float(world[0])
                y = float(world[1])
            else:
                x = random.uniform(-0.8, 0.8)
                y = 1.8
        else:
            x = random.uniform(-0.8, 0.8)
            y = 1.8

        shape_type = "circle" if random.random() < 0.5 else "square"
        local_shape = self.manager.generate_shape(shape_type, pts)
        local_shape *= float(CONFIG.render.foe_shape_scale)

        hp = float(CONFIG.foe.start_hp)
        if self._hp_ramp_started_at_s is not None:
            t = max(0.0, float(self.run_time_s - self._hp_ramp_started_at_s))
            hp *= 1.0 + t * float(self.hp_ramp_per_s) * float(self.difficulty)

        foe = Foe(
            id=self.next_foe_id,
            pool_idx=indices,
            pos=[float(x), float(y)],
            hp=float(hp),
            max_hp=float(hp),
            local_shape=local_shape,
            radius=float(CONFIG.foe.radius),
        )
        self.next_foe_id += 1
        self.foes.append(foe)

    def _update_foes(self, dt: float) -> None:
        speed = float(CONFIG.foe.move_speed)
        dead_indices: list[int] = []

        for i, foe in enumerate(self.foes):
            if not foe.attacking:
                dx = float(self.player_pos[0]) - float(foe.pos[0])
                dy = float(self.player_pos[1]) - float(foe.pos[1])
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1e-6:
                    foe.pos[0] += (dx / dist) * speed * float(dt)
                    foe.pos[1] += (dy / dist) * speed * float(dt)

                if self._in_attack_zone(foe):
                    foe.attacking = True
                    foe.attack_timer = 0.0

                ndc = self._world_to_ndc(foe.pos[0], foe.pos[1], 0.0)
                if ndc is not None and float(ndc[1]) < -1.25:
                    dead_indices.append(i)
                    self._hide_foe(foe)
                    self.manager.free_foe(foe.pool_idx)
                continue

            foe.attack_timer -= float(dt)
            if foe.attack_timer <= 0.0:
                dmg = max(1.0, float(self.foe_attack_damage) * float(self.difficulty))
                self.player_hp -= dmg
                foe.attack_timer += float(self.foe_attack_interval_s)

                if self.player_hp <= 0.0:
                    self.player_hp = 0.0
                    self.is_game_over = True
                    break

        for i in reversed(dead_indices):
            self.foes.pop(i)

    def _auto_fire(self, dt: float) -> None:
        self.fire_timer -= float(dt)
        if self.fire_timer > 0.0:
            return

        closest_foe = None
        min_dist = 1000.0
        px, py = self.player_pos

        for foe in self.foes:
            dx = foe.pos[0] - px
            dy = foe.pos[1] - py
            d = math.sqrt(dx * dx + dy * dy)
            if d < min_dist:
                min_dist = d
                closest_foe = foe

        if closest_foe is None:
            return

        self._fire_beam(closest_foe)
        self.fire_timer = float(self.fire_rate)

    def _fire_beam(self, target: Foe) -> None:
        pts = int(CONFIG.projectile.points)
        indices = self.manager.allocate_beam(pts)
        if indices is None:
            return

        start_pos = list(self.player_pos)

        speed = float(CONFIG.projectile.speed)
        dx = target.pos[0] - start_pos[0]
        dy = target.pos[1] - start_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.001:
            dist = 0.001

        vel = [dx / dist * speed, dy / dist * speed]

        proj = Projectile(
            id=self.next_projectile_id,
            pool_idx=indices,
            pos=start_pos,
            vel=vel,
            damage=float(CONFIG.projectile.damage),
            active=True,
            radius=float(CONFIG.projectile.radius),
        )
        self.next_projectile_id += 1
        self.projectiles.append(proj)

    def _update_projectiles(self, dt: float) -> int:
        dead_indices: list[int] = []
        dead_foe_indices: list[int] = []
        kills = 0

        for i, proj in enumerate(self.projectiles):
            proj.pos[0] += proj.vel[0] * float(dt)
            proj.pos[1] += proj.vel[1] * float(dt)

            if not (-1.5 < proj.pos[0] < 1.5 and -2.0 < proj.pos[1] < 2.5):
                dead_indices.append(i)
                self._hide_projectile(proj)
                continue

            hit_foe_index = None
            for j, foe in enumerate(self.foes):
                dx = foe.pos[0] - proj.pos[0]
                dy = foe.pos[1] - proj.pos[1]
                r = float(foe.radius + proj.radius)
                if dx * dx + dy * dy < (r * r):
                    hit_foe_index = j
                    break

            if hit_foe_index is None:
                continue

            foe = self.foes[hit_foe_index]
            foe.hp -= float(proj.damage)
            dead_indices.append(i)
            self._hide_projectile(proj)

            if foe.hp <= 0.0:
                dead_foe_indices.append(hit_foe_index)
                self._hide_foe(foe)
                self.manager.free_foe(foe.pool_idx)
                kills += 1

        for i in sorted(set(dead_indices), reverse=True):
            if i < len(self.projectiles):
                self.projectiles.pop(i)

        for j in sorted(set(dead_foe_indices), reverse=True):
            if j < len(self.foes):
                self.foes.pop(j)

        return kills

    def _hide_foe(self, foe: Foe) -> None:
        count = foe.pool_idx[1] - foe.pool_idx[0]
        empty = torch.randn((count, 3), device=self.manager.device) * 100.0
        self.manager.update_targets({foe.pool_idx: empty})

    def _hide_projectile(self, proj: Projectile) -> None:
        count = proj.pool_idx[1] - proj.pool_idx[0]
        empty = torch.randn((count, 3), device=self.manager.device) * 100.0
        self.manager.update_targets({proj.pool_idx: empty})

    def _sync_sim(self) -> None:
        updates: dict[tuple[int, int], torch.Tensor] = {}

        for foe in self.foes:
            offset = torch.tensor([foe.pos[0], foe.pos[1], 0.0], device=self.manager.device)
            updates[foe.pool_idx] = foe.local_shape + offset

        for proj in self.projectiles:
            pts = proj.pool_idx[1] - proj.pool_idx[0]
            blob = torch.randn((pts, 3), device=self.manager.device) * 0.02
            center = torch.tensor([proj.pos[0], proj.pos[1], 0.0], device=self.manager.device)
            updates[proj.pool_idx] = center + blob

        if updates:
            self.manager.update_targets(updates)
