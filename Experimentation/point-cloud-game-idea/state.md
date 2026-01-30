# Point Cloud Game Prototype — State Snapshot

This file is a “restart context” snapshot so a new chat/agent can pick up without rereading everything.

## Repo / How to Run
- Location: `Experimentation/point-cloud-game-idea/`
- Entrypoint: `main.py`
- Run: `uv run main.py` (you already ran `uv sync` successfully)

## High-Level Goal (from `plans/prototype-plan.md`)
- Core loop: stationary base/player → auto-fire/auto-cast → swarms → death.
- Look: point-cloud visuals (glowing point sprites), minimal UI.
- Constraints:
  - Reuse patterns/code, but don’t import `3d-point-cloud-weave` as a dependency/package.
  - No hard caps in-game (no max enemies/projectiles/pickups).
  - Plan stays “question-first”; decisions should be confirmed with you.

## Confirmed Gameplay Spec (from you)
- Difficulty: `diff` exists; for now `diff = 1` (chosen at run start later).
- Spawn acceleration:
  - It should **never stop**.
  - When “~100 foes on screen” is reached: **continue acceleration**, and **start HP-ramping newly spawned foes**.
- Camera: current camera is acceptable; keep it.
- Player/base positioning:
  - Player is bottom-middle of screen.
  - Player character should be visually smaller (relative to screen).
- “Bottom 20% attack zone”:
  - When a foe reaches the bottom ~20% of the screen, it starts attacking.
  - Each attack always deals some HP damage.
  - Player starts with **3000 HP**.

## Current Implementation (as of this snapshot)

### Files / Modules
- `main.py`: Qt app bootstrap; sets GL format; opens `point_cloud_game.ui.GameWindow`.
- `point_cloud_game/ui.py`:
  - A full-screen-ish fixed-size window (540x960) with an overlay menu.
  - A `SpawnBar` widget intended to show time-to-next-spawn.
  - A HUD label showing HP, foe count, spawn timer/rate.
- `point_cloud_game/gl_widget.py`:
  - ModernGL point sprite renderer drawing `WeaveSim.pos` with additive blending.
  - Tick loop calls `game.set_view(...)`, `game.update(dt)`, `sim.step(dt)`.
- `point_cloud_game/sim.py`: `WeaveSim` point “targets → positions” simulation.
- `point_cloud_game/targets.py`: samples targets/colors/intensity from `assets/weave.png`.
- `point_cloud_game/sim_adapter.py`: `PointCloudManager`
  - Builds a single large buffer (`total_points=250k`).
  - Reserves ~60k points for the weave/player, rest for dynamic entities.
  - Implements a small free-list for reusing foe ranges.
  - Centers the weave point cloud at a configurable player anchor.
- `point_cloud_game/game.py`: `Game`
  - Tracks player HP, foes, projectiles, spawn timer/rate, and kill-driven spawn acceleration.
  - Auto-fires projectile “magic” at the closest foe.
  - Foes move toward the player and enter an attack mode in the bottom zone.
  - “Visible foes” is measured by projecting foes to NDC; once the soft target is hit, newly spawned foes get HP ramp.
  - Foe spawn position is computed using NDC→world (z=0 plane), so “spawn slightly off-screen” is camera-consistent.

### Config
- `config.py` (root, next to `main.py`) exists for tuning:
  - `CONFIG.player`: HP and the player anchor (`x`, `y`) used to position the weave point cloud.
  - `CONFIG.spawning`: spawn rate, spawn NDC location, soft target count.
  - `CONFIG.foe`: base HP, HP ramp, move speed, attack cadence/damage, etc.
  - `CONFIG.projectile`: fire rate, speed, damage, etc.
  - `CONFIG.render`: foe point counts and shape scale.
  - `CONFIG.ui`: spawn bar size/margins.

## What You Reported (current issues)
- “There is no new game.”
- You do not see the top spawn bar.
- You do not see “settings / fine-tuning looks” UI like in the older 3D prototype.
- On load, you see only the character spawn in and sit there (no foes spawning/attacking).

No fixes were requested for these issues in the latest instruction; this snapshot records them for the next session.

## Planned Roadmap (from the plan + updated with your answers)
1) Verify current prototype runs (env + runtime blockers)
2) Align camera and world bounds (keep current camera; ensure bottom-mid anchor; define bottom 20% zone)
3) Finish core combat loop (projectiles, collisions, cleanup, kill-driven spawn accel, “~100 visible” trigger)
4) Add base HP and game over (overlay, restart)
5) Implement XP and level-ups (picker + upgrade tags)
6) Match spawn/scaling spec (soft target + HP ramp, miniboss cadence, boss cadence + pause + 4x spawn pressure)
7) Add mini bosses and bosses (rewards: 1 free level-up, 5 free level-ups)

## Open Questions Remaining (deferred)
- Exact initial value/formula for “spawn-speedup per kill” (currently a tunable constant).
- Exact HP ramp curve after the soft target (currently linear-in-time multiplier on newly spawned foes).
- Boss/miniboss probability ramp mechanics (“until all foes are mini bosses”) not implemented.
- Cards system is TBD.

## Notes for a Future Restart
- If UI elements aren’t visible, likely culprits are widget stacking/attributes or menu state blocking (e.g., `Game.paused` / menu overlay).
- If foes “spawn” but aren’t visible, likely culprits are NDC→world conversion, world scale, or render-time depth/point-size interactions.

