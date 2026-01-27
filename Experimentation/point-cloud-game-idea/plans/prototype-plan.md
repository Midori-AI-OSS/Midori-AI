# Point Cloud Game Prototype Plan (restart; question-first)

Status: draft (please comment; we’ll revise this file repeatedly)

## 1) First question (please answer before we lock anything else)
1) **Where will the code live, given “reuse but cannot import”?**
   - Current answer: copy only the minimum needed files (e.g., `gl_widget.py`, `camera.py`, `style.py`) and rename to `point_cloud_game/*`.

## 2) Constraints (captured from you; no assumptions)
- **Reuse, but no imports:** we will reuse `3d-point-cloud-weave` code, but we will not “import it as a dependency/package”.
- **No hard caps in-game:** we will not add “max enemies / max projectiles / max pickups” style hard limits.
- **Plan behavior:** I’ll ask before making decisions; this plan stays open for comments and rewrites.

## 3) Prototype goal (tight definition; editable)
- **Core loop:** stationary base/player → auto-fire / auto-cast → swarms → death.
- **Run structure:** frequent level-ups; build identity by ~5 minutes.
- **Look:** point-cloud visuals (glowing point sprites); minimal non-diegetic UI.

## 3.1) In-run pacing spec (spawns + scaling; from you)
### Camera + “on screen” definition (from you)
- Camera is **locked top-down**.
- Player party is anchored at the **bottom of the screen**.
- Foes **enter from the top** and should **spawn slightly off-screen** so they don’t pop into frame.
- “~100 foes on screen” means **visible in the camera view**.

### Normal foes
- Spawn cadence starts at **1 foe every 3 seconds**.
- **Each kill** speeds up the spawn cadence by a **set %** until the screen has **~100 foes on screen**.
- After that “~100” point is reached, **only newly spawned foes** start receiving an **HP buff ramp** (slow ramp).
- Normal foe HP starts at **100**.

### Mini bosses
- Spawn a mini boss every **2.5 minutes**.
- Mini bosses grant **1 free level up** to the character that kills it.
- Mini boss HP starts at **10x normal**, with a minimum of **`1000 * diff`** (definition of `diff` TBD).
- Mini boss HP ramps up at **2x the speed** of normal foes.
- Mini boss spawns also speed up “until all foes are mini bosses”.

### Bosses
- Spawn a boss every **15 minutes**.
- **Pre-boss pause:** stop spawning foes/mini bosses for **~5 seconds** before spawning the boss.
- Once the boss is spawned/on screen: spawn foes at **4x** the normal foe spawn rate until the boss is killed.
- During bosses, “~100 foes on screen” becomes **~200ish on screen** (tunable).
- Boss HP starts at **500x mini boss HP**.
- Boss kill grants **5 free level ups**.

### Cards (stub for later)
- Mini bosses grant **1 card**.
- Bosses grant **1 card**.
- Card system details: TBD (you’ll share later).

## 3.2) Open parameters to confirm (to avoid me “deciding”)
- Normal-foe **spawn-speedup per kill**: tune during playtests (initial value + formula TBD).
- Is “~100 foes” a **soft target** (continue spawning, but start HP ramp) or does spawn acceleration stop exactly there?
- Define `diff` used in **`1000 * diff`** mini boss HP minimum.
- “Until all foes are mini bosses”: is this a **probability ramp**, a **replacement rule**, or something else?
- Boss “4x spawn rate”: multiply the **current** normal-foe cadence, or reset to a known baseline?
- Boss “~200ish on screen”: should that be a **soft target** like the normal “~100” behavior?
- Performance governor idea: if we detect lag, do you want us to **reduce spawn pressure** and compensate by **buffing HP/damage**, or do you want **no runtime performance-based difficulty changes**?

## 4) What we’re reusing (source references)
- **App shell + docks:** `Experimentation/3d-point-cloud-weave/point_cloud_weave/ui.py`
- **OpenGL widget + tick loop:** `Experimentation/3d-point-cloud-weave/point_cloud_weave/gl_widget.py`
- **Camera + cursor→world:** `Experimentation/3d-point-cloud-weave/point_cloud_weave/camera.py`
- **Styling:** `Experimentation/3d-point-cloud-weave/point_cloud_weave/style.py`
- **(Optional) batched sim patterns:** `Experimentation/3d-point-cloud-weave/point_cloud_weave/sim.py`

## 5) “No hard caps” approach (policy-based, not limit-based)
Instead of caps, we’ll control load by policies you approve:
- **Budget target:** choose a frame-time target and prioritize keeping the game responsive.
- **Degradation choices (examples):** fuse far-away swarms, reduce VFX density first, probabilistic spawn thinning, cluster-based damage resolution, lower point detail for off-center entities.

## 6) Milestones (each ends in a runnable, reviewable slice)
### M0 — Window + render loop (no gameplay)
- A window that renders a basic arena + base and updates with a stable timestep policy.

### M1 — Enemy approach + loss
- Enemies spawn and approach the base; base loses HP; game over UI appears.
- Uses the **normal-foe spawn cadence start** (1 per 3s).

### M2 — Auto-fire + kills + XP
- Auto-fire or auto-cast kills enemies; XP drops; level-ups occur.
- Includes **kill-driven spawn ramp** up to the “~100 foes” point (per spec).

### M3 — Level-up picker + tagged upgrades
- A simple picker that offers upgrades with tags; upgrades visibly change behavior.

### M4 — Readability pass (still prototype)
- Ensure enemies/projectiles/build choices are readable with point-cloud visuals.

### M5 — Mini bosses (cadence + reward)
- Add mini boss spawns, scaling, and **free level up** reward (per spec).

### M6 — Boss event (cadence + spawn pause + reward)
- Add boss cadence, pre-boss pause, 4x spawn pressure during boss, and rewards (per spec).

## 7) Comment / decision log (please write here)
- Your answers:
  - Q1:
- Decisions we locked:
  - Camera is locked top-down; party at bottom; foes enter from top (spawn slightly off-screen).
  - “On screen” means visible in the camera view.
- Changes you want:
  - (add)
