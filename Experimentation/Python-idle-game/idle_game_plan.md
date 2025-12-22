DO NOT EDIT — generated planning doc for idle-game agents

Notes:
- Purpose: concise, machine-friendly planning document to hand off to extraction / implementation agents for a Python idle game using characters from the Endless-Autofighter codebase.
- How to use: save this file as `.codex/temp/idle_game_plan.md` and use it as a task payload for agents. Sections include: project summary, per-character summaries (extracted from backend/plugins/characters), GUI framework research + recommendation, MVP feature list, JSON schema example, and next actions (agents).
- Scope: I inspected the repository path  and summarized all character plugin files found there. Asset lookup hints point to frontend asset locations:  and .

## Project Summary and Goals
TL;DR: Build a small cross-platform Python idle / companion UI that exposes the Endless-Autofighter character roster for idle progression and light interaction. The app will show per-character windows (portrait + stats), run background timers for passive growth, allow minimal interactions (activate abilities / inspect), and offer save/load and a simple chat/diary interface for characters (leveraging existing LLM hooks if available).

Goals:
- Provide a desktop-friendly idle experience (Windows / macOS / Linux).
- Reuse Endless-Autofighter character data and assets (portraits, summon art).
- Minimal game loop: passive growth ticks + basic stat changes and progress bars.
- Handoffable tasks for specialized agents: extraction, GUI scaffold, asset checklist.

---

## Character Summaries (extracted from backend/plugins/characters/)
Notes: each entry shows id, short lore (from  when present), key class fields, growth notes, and asset hints. If a character sets custom base stats in , I've listed those values; otherwise assume default PlayerBase stats in  (hp 1000, base_atk 100, defense 50, etc.). Damage type may be a loader call — I show the canonical type when obvious.

- id: `carly` — name: Carly
  - Short lore: A protective sim-human guardian converting offensive power into shield barriers.
  - Key stats/fields: char_type B, gacha_rarity 5, damage_type Light, passives `["carly_guardians_aegis"]`, special_abilities `["special.carly.guardian_barrier"]`, .
  - Explicit base stat changes: mitigation 4.0, defense 220, max_hp 1600, base_aggro 2.35, damage_reduction_passes 2, hp set to max.
  - Growth mechanics: inherits PlayerBase ,  and has  (maps gain). Level-up passive likely via `player_level_up_bonus` style; Carly herself has no unique level-up code beyond stats.
  - Assets: portrait id `carly` (look for `frontend/src/lib/assets/characters/carly.png` or folder). May have associated voice sample or portrait pool.

- id: `kboshi` — name: Kboshi
  - Short lore: Master of dark/void energy, cycles of destructive flux.
  - Key stats: char_type A, gacha_rarity 5, damage_type Dark, passives `["kboshi_flux_cycle"]`.
  - Growth: standard PlayerBase leveling; no explicit base stat overrides in plugin.
  - Assets: portrait `kboshi`.

- id: `lady_echo` — name: LadyEcho
  - Short lore: Inventor whose lightning resonances cost her time; static-based echoes.
  - Key stats: char_type B, gacha_rarity 5, damage_type Lightning, passives `["lady_echo_resonant_static"]`, .
  - Growth: standard PlayerBase leveling.
  - Assets: `lady_echo` portrait gallery.

- id: `lady_darkness` — name: LadyDarkness
  - Short lore: Aasimar sorceress commanding an eclipsing veil and precise entropy magic.
  - Key stats: char_type B, gacha_rarity 5, damage_type Dark, passives `["lady_darkness_eclipsing_veil"]`.
  - Growth: standard.
  - Assets: `lady_darkness`.

- id: `jennifer_feltmann` — name: Jennifer Feltmann
  - Short lore: Veteran programming/robotics teacher; debuff-themed kit ("bad student").
  - Key stats: char_type B, gacha_rarity 5, damage_type Dark, passives `["bad_student"]`, voice_gender `female`.
  - Growth: standard;  sets hp = max_hp.
  - Assets: `jennifer_feltmann`.

- id: `lady_fire_and_ice` — name: LadyFireAndIce
  - Short lore: 6★ dual-element elemental master that switches between fire and ice personas.
  - Key stats: char_type B, gacha_rarity 6, damage_type: dynamic choice Fire/Ice, passives `["lady_fire_and_ice_duality_engine"]`.
  - Growth: standard.
  - Assets: `lady_fire_and_ice`.

- id: `ixia` — name: Ixia
  - Short lore: Tiny titan lightning wielder (compact but powerful).
  - Key stats: char_type A, gacha_rarity 5, damage_type Lightning, passives `["ixia_tiny_titan"]`, special `["special.ixia.lightning_burst"]`.
  - Growth: standard.
  - Assets: `ixia`.

- id: `lady_light` — name: LadyLight
  - Short lore: Aasimar who affirms existence with radiant aegis; sister to LadyDarkness.
  - Key stats: char_type B, gacha_rarity 5, damage_type Light, passives `["lady_light_radiant_aegis"]`.
  - Growth: standard.
  - Assets: `lady_light`.

- id: `hilander` — name: Hilander
  - Short lore: Brewmaster who turns combat into alchemical explosions.
  - Key stats: char_type A, gacha_rarity 5, damage_type: random (choice of ALL_DAMAGE_TYPES), passives `["hilander_critical_ferment"]`.
  - Growth: standard.
  - Assets: `hilander`.

- id: `graygray` — name: Graygray
  - Short lore: Tactical counter maestro—turns enemy attacks into counters.
  - Key stats: char_type B, gacha_rarity 5, damage_type: random, passives `["graygray_counter_maestro"]`, special `["special.graygray.counter_opus"]`.
  - Growth: standard.
  - Assets: `graygray`.

- id: `casno` — name: Casno
  - Short lore: Stoic pyrokinetic who weaponizes tactical recovery (Relaxed stacks).
  - Key stats: char_type A, gacha_rarity 5, damage_type Fire, passives `["casno_phoenix_respite"]`, voice_gender `male`.
  - Growth: has resource stacking mechanic described in  (stacking "Relaxed" every five attacks, overflow gives self-heal + stat boons) — this is a growth/combat mechanic, not long-term EXP growth.
  - Assets: `casno`.

- id: `bubbles` — name: Bubbles
  - Short lore: Aquatic, bubble-based chain-reaction attacker (non-humanoid).
  - Key stats: char_type A, gacha_rarity 5, damage_type: random, passives `["bubbles_bubble_burst"]`.
  - Growth: standard.
  - Assets: `bubbles`.

- id: `becca` — name: Becca
  - Short lore: Artistic sim-human who coordinates elemental menagerie.
  - Key stats: char_type B, gacha_rarity 5, damage_type: random, passives `["becca_menagerie_bond"]`, special `["special.becca.menagerie_convergence"]`.
  - Growth: standard.
  - Assets: `becca`.

- id: `ally` — name: Ally
  - Short lore: Versatile support who overloads enemy systems; multi-element focus.
  - Key stats: char_type B, gacha_rarity 5, damage_type: random, passives `["ally_overload"]`, special `["special.ally.overload_cascade"]`.
  - Growth: standard.
  - Assets: `ally`.

- id: `slime` — name: Slime
  - Short lore: Training dummy / unobtainable practice target.
  - Key stats: gacha_rarity 0, ui_non_selectable True, plugin_type `player` (inherits PlayerBase), flagged as non-selectable in UI.
  - Growth: N/A for roster; used for tests.
  - Assets: possible generic slime art.

- id: `ryne` — name: Ryne
  - Short lore: 6★ Oracle of Light; restoration and shielding with blades/gunblade usage.
  - Key stats: char_type B, gacha_rarity 6, damage_type Light, passives `["ryne_oracle_of_balance"]`, .
  - Growth: standard.
  - Assets: `ryne`.

- id: `player` — name: Player
  - Short lore: Customizable main character; central leveling mechanics.
  - Key stats: char_type C, damage_type Fire (default), passives `["player_level_up_bonus"]`.
  - Growth: central to game: , ,  present; this is template for growth rules.
  - Assets: uses generic player portrait(s).

- id: `persona_light_and_dark` — name: PersonaLightAndDark
  - Short lore: Guardian brother trading between light and dark to protect allies (high-aggro/tank).
  - Key stats: char_type A, gacha_rarity 6, damage_type: choice Light/Dark, passives `["persona_light_and_dark_duality"]`.
  - Explicit base stat overrides: mitigation 4.0, defense 240, max_hp 1700, base_aggro 2.35, damage_reduction_passes 2, hp set to max.
  - Growth: standard.
  - Assets: `persona_light_and_dark`.

- id: `persona_ice` — name: PersonaIce
  - Short lore: Cryokinetic tank shielding sisters; meditative ice cycle that hardens then heals.
  - Key stats: char_type A, gacha_rarity 5, damage_type Ice, passives `["persona_ice_cryo_cycle"]`.
  - Explicit base stat overrides: mitigation 4.0, defense 210, max_hp 1650, base_aggro 2.35, hp set to max.
  - Growth: standard.
  - Assets: `persona_ice`.

- id: `mezzy` — name: Mezzy
  - Short lore: Catgirl maid who devours incoming damage to grow (gluttonous bulwark).
  - Key stats: char_type B, gacha_rarity 5, damage_type: random, passives `["mezzy_gluttonous_bulwark"]`.
  - Growth: combat-driven scaling (absorbing damage increases power) vs. long-term EXP.
  - Assets: `mezzy`.

- id: `luna` — name: Luna
  - Short lore: Precise starlit scholar; summons lunar swords and has a lunar reservoir passive.
  - Key stats: char_type B, gacha_rarity default, damage_type Generic by default, passives , .
  - Explicit fields: / values, , ,  and custom  logic (special spawn rules; disallows spawning when in party; boss spawn weighting with floor-based multipliers).
  - Growth/Mechanics: complex summon + passive system, Luna's passive interacts with SummonManager and has unique event hooks (swords, charge, prime healing).
  - Assets: `luna` +  summon art indicated by frontend docs.

- id: `lady_wind` — name: LadyWind
  - Short lore: Aeromancer twin; bleeding winds with suspended crystallizing droplets; guards allies.
  - Key stats: char_type B, gacha_rarity 5, damage_type Wind, passives `["lady_wind_tempest_guard"]`.
  - Growth: standard.
  - Assets: `lady_wind`.

- id: `lady_storm` — name: LadyStorm
  - Short lore: 6★ tempest caller; can produce devastating area storms; blend of wind/lightning.
  - Key stats: char_type B, gacha_rarity 6, damage_type choice Wind/Lightning, passives `["lady_storm_supercell"]`.
  - Growth: standard.
  - Assets: `lady_storm`.

- id: `lady_of_fire` — name: LadyOfFire
  - Short lore: Pyromancer whose infernal momentum grows with victories; dissociative schizophrenia as lore element.
  - Key stats: char_type B, gacha_rarity 5, damage_type Fire, passives `["lady_of_fire_infernal_momentum"]`.
  - Growth: combat momentum mechanic (heat increases with victories).
  - Assets: `lady_of_fire`.

- id: `lady_lightning` — name: LadyLightning
  - Short lore: Electra — manic lightning wielder who escaped a lab; unpredictable surges.
  - Key stats: char_type B, gacha_rarity 5, damage_type Lightning, passives `["lady_lightning_stormsurge"]`.
  - Growth: standard.
  - Assets: `lady_lightning`.

Summary notes:
- Most characters follow  defaults unless they override via  with  and other flags (mitigation/defense/max_hp/base_aggro).
- Passive names are present and needed for any combat simulation; these passives themselves live in  (not covered here) and may reference UI or long-term growth.
- Asset locations: portraits -> `frontend/src/lib/assets/characters/<id>.png` or galleries; summons -> .

---

## GUI Frameworks (comparison & recommendation)
Three frameworks researched (practical for an idle game with multiple windows and background updates):

1) PySide6 / PyQt6 (Qt)
- Short description: Full-featured native-looking toolkit with widgets, layouts, multiple windows, dialogs, model/view patterns, and QTimer for periodic tasks.
- Pros: Mature, performant, excellent widgets, native look on platforms, multiple windows and dialogs supported, well-documented, built-in signals/slots make threads/events safe, good for complex UIs.
- Cons: Heavier runtime; PyQt licensing (GPL/commercial) vs PySide6 (LGPL) — choose `PySide6` to avoid GPL; large binary for packaging.
- Packaging ease: Good — `PyInstaller`, `briefcase` or `pynsist` can create cross-platform apps (bigger binary sizes). Works well on Windows/Linux/macOS.
- Python package name: `PySide6` (or `PyQt6`).
- Multiple windows: Yes.
- Background timers/threads/event-loop integration: Yes — use `QTimer` for periodic updates; `QThread` or signals for background work.
- Recommended for: Full-featured desktop idle app with multiple windows and stable timer integration.

2) Tkinter (builtin standard library)
- Short description: Lightweight, built-in GUI available in the Python stdlib; simple widgets and canvas.
- Pros: Preinstalled on most Python installs, minimal dependencies, easy to package and distribute, low resource usage.
- Cons: Older look-and-feel, less polished widgets, more manual layout management, threading requires care (use `after()` for periodic updates on main thread).
- Packaging: Very easy with `PyInstaller`, minimal binary size.
- Python package name: builtin (`tkinter` module); on some Linux distros need `python3-tk`.
- Multiple windows: Yes (Toplevel windows).
- Background timers/threads/event-loop integration: Yes, via `after()` for periodic updates; threads can be used but must marshal results to main thread.
- Recommended for: Quick prototypes, very small MVPs, or when avoiding external dependencies.

3) Kivy
- Short description: Modern, touch-enabled, GPU-accelerated UI toolkit with declarative layouts; mobile-friendly.
- Pros: Great for fluid animations, cross-platform (including mobile), GPU-accelerated UI.
- Cons: Larger dependency surface, different look than native desktop, packaging on macOS/Windows more involved (size and complexity), steeper learning curve for standard desktop UI paradigms.
- Packaging: Possible (Buildozer for Android, PyInstaller for desktop) but heavier; extra bundling steps.
- Python package name: `kivy`.
- Multiple windows: Limited/more complex — Kivy historically focused on single-window; multiple windows possible but less conventional.
- Background timers/threads/event-loop integration: Yes (Clock.schedule_interval), but integration specifics differ from typical desktop toolkits.
- Recommended for: Touch-first apps or animated interfaces; less ideal for multi-window desktop MVP.

Recommendation: PySide6 (Qt) as best fit.
- Reason: Desktop-oriented, robust multiple-window support, strong event/timer model (`QTimer`) for idle ticks, better native look, and easier to implement per-character windows with status bars. Packaging is straightforward with `PyInstaller` and common practice for cross-platform desktop apps. If dependency size is a concern and a simple UI is enough, `Tkinter` is a fallback for faster prototyping.

---

## Minimal MVP Feature List
- Main menu:
  - Start / Load / Save / Settings / Exit
- Roster view:
  - Grid/list of characters (portrait thumbnails + name + rarity)
  - Click to open per-character window
- Per-character windows:
  - Portrait (static image or gallery), name, short lore
  - Stat bars: HP, Max HP, Attack, Defense, Ultimate charge / progress
  - Passive list and special ability buttons (disabled initially)
  - Passive growth indicator and last-tick time
- Passive / Background growth:
  - Periodic ticks (configurable; default 1s or 5s) that apply passive growth rules (use PlayerBase-like semantics)
  - Visible progress increments (bars + numeric)
- Simple chat/diary interface:
  - Text box to "message" a character (optionally call  if local TTS/LLM available)
  - Character replies saved to memory (simulate  or show cached responses)
- Save / Load:
  - Persist characters' levels, exp, hp, ultimate_charge, passive states, and any assets links in a single JSON file
- Asset manager:
  - Locate and map portraits from the Endless-Autofighter frontend assets path (provide fallback if missing)
- Minimal settings:
  - Tick rate, window scaling, chosen GUI theme (light/dark)
- Optional:
  - Simple "combat simulation" toggle that runs a short scripted encounter to exercise passives (for QA)

---

## Suggested data format for characters (example JSON schema)
- Purpose: canonical character data for the idle game (derived from plugin fields). Stored per character in  or a single .

Example JSON schema (concise)
{
  "id": "string",
  "name": "string",
  "short_lore": "string",
  "full_lore": "string",
  "char_type": "A|B|C",
  "gacha_rarity": "number",
  "damage_type": "string",
  "passives": ["string"],
  "special_abilities": ["string"],
  "ui": {
    "portrait": "path|url",
    "portrait_pool": "string|null",
    "actions_display": "string|null",
    "non_selectable": "bool"
  },
  "base_stats": {
    "max_hp": "int",
    "atk": "int",
    "defense": "int",
    "mitigation": "float",
    "base_aggro": "float"
  },
  "runtime_defaults": {
    "hp": "int",
    "level": "int",
    "exp": "int",
    "ultimate_charge": "int",
    "ultimate_charge_capacity": "int"
  },
  "growth": {
    "stat_gain_map": {"stat":"map_to_stat"},
    "exp_multiplier": "float"
  },
  "notes": "string - plugin file path and any special mechanics (e.g., Luna's summon coordinator)"
}

Example (Carly):
{
  "id": "carly",
  "name": "Carly",
  "short_lore": "A protective sim-human guardian converting power to shields.",
  "char_type": "B",
  "gacha_rarity": 5,
  "damage_type": "Light",
  "passives": ["carly_guardians_aegis"],
  "special_abilities": ["special.carly.guardian_barrier"],
  "ui": {"portrait": "assets/characters/carly.png", "actions_display": "number"},
  "base_stats": {"max_hp":1600, "defense":220, "mitigation":4.0, "base_aggro":2.35},
  "runtime_defaults": {"hp":1600, "level":1, "exp":1, "ultimate_charge":0, "ultimate_charge_capacity":null},
  "growth": {"stat_gain_map":{"atk":"defense"}, "exp_multiplier":1.0}
}

Storage recommendations:
- Put canonical plugin-derived JSON in  for the idle game. A single  should list available IDs and portrait file hints (to speed UI load).
- Keep a runtime save (per-user) with stripped state:  containing only fields that change (hp, exp, level, mastery, passive cooldowns).

---

## Next Actions / Agent Tasks (3–6 agents suggested)
1) Agent: Character Data Extractor (automated)
   - Task:
     - Read  and extract canonical fields for each plugin class into .
     - Extract: id, name, summarized_about/full_about, char_type, gacha_rarity, damage_type (string), passives, special_abilities, ui hints (actions_display, ui_portrait_pool, ui_non_selectable), any  overrides in  (translate to base_stats), any custom class variables (spawn_weight_multiplier, ultimate_charge_capacity).
     - Create  listing all characters with a canonical portrait path guess and plugin file reference.
   - Notes: Use AST parsing (or import plugin modules carefully) — prefer static parsing to avoid runtime imports. If dynamic imports are used, isolate in sandbox.

2) Agent: GUI Scaffold (implementation)
   - Task:
     - Scaffold a PySide6 project (recommended) with:
       - Main window with roster grid.
       - Per-character window template: portrait, stat bars, passive list, chat box.
       - Background tick scheduler using `QTimer` to dispatch periodic "idle_tick" events (default every 1s; configurable).
       - Save and Load handlers (read/write JSON saves).
     - Provide `requirements.txt` with `PySide6` and a minimal runner `run_idle_game.py`.
   - Deliverables: `gui/` folder with PySide6 app skeleton and  for dev instructions.

3) Agent: Asset Collector / Checklist
   - Task:
     - Inspect  and  (Endless-Autofighter repo) and produce:
       - Mapping CSV/JSON:  (portrait single or gallery).
       - Missing assets checklist: characters without portraits.
       - Suggested placeholder images (fallback) for missing items.
   - Deliverable: , .

4) Agent: Save/Load and Persistence Agent
   - Task:
     - Implement JSON save/load API for runtime state (per-character runtime defaults + global settings).
     - Include simple migration logic and ephemeral autosave.
     - Provide an example save with two sample character states for QA.

5) Agent: Chat/LLM Integration Agent (optional)
   - Task:
     - Integrate a stub chat interface that calls  asynchronously if local LLM/TTs are installed, else fall back to canned replies.
     - Persist chat history to character runtime state (mimic ).

Optional extras:
- Packaging Agent: Build `PyInstaller` spec and sample packaged builds for Linux and Windows.
- UX polish: portrait galleries, small animated progress bars, tray minimization.

---

## Implementation Notes & Constraints
- Extraction: Prefer static parsing of plugin files (AST) to avoid executing game runtime and importing external dependencies (LLM bindings). If dynamic import is needed, sandbox imports and fall back to reading class-level assignments via regex/AST.
- Assets: Frontend uses `frontend/src/lib/assets/characters/<name>.png` or  folder; fallback behavior exists. Use this to map portrait files.
- Passive/system logic: Many characters rely on passive modules and SummonManager — the idle UI needs only to present passives and simulate simple ticks; full combat replication is out of scope for MVP.
- Respect IP & licenses: The module uses many assets; when packaging or shipping, follow original licensing in repository.

---

## Quick File/Path References (for agent handoffs)
- Character plugins: Midori-AI-Mono-Repo/Endless-Autofighter/backend/plugins/characters/
- Base classes:  and 
- Frontend portraits: .../Endless-Autofighter/frontend/src/lib/assets/characters/
- Summons: .../Endless-Autofighter/frontend/src/lib/assets/summons/
- Passive implementations: .../Endless-Autofighter/backend/plugins/passives/
- Suggested output (idle app): `idle-game/` top-level scaffold, , , `idle-game/gui/`.

---

If you want, I can:
- Produce the `Character Data Extractor` agent spec (detailed step-by-step AST extraction plan and example code).
- Scaffold the PySide6 GUI skeleton (files + run instructions).
- Generate the  with current extracted entries (I already parsed plugin files; I can generate the JSON files into `.codex/temp/`).

Which of the above tasks should I prepare next?