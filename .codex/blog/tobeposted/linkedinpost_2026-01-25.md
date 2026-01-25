# Strategic Pauses and Infrastructure Evolution — Midori AI (January 25, 2026)

This is the quiet period between major launches—no dramatic PRs, no breaking changes, just infrastructure planning and lateral thinking that changes everything three months later.

Case in point: Luna played Daggerheart this week, and her tabletop character L.U.N.A (Logical Universal Nimble Assistant) is transforming into W.E.A.V.E. She's still working out the acronym and mechanics, but the visual is locked in: a constellation figure composed of golden and green particle effects against a starry void. It's the kind of creative work that happens in the margins of technical projects, and it's getting its own space in Website-Blog's lore infrastructure.

At Midori AI, we're balancing active development with deliberate planning. This week brings hardware experiments that reframe mobile workflows, repository structure improvements that reduce cognitive friction, and a critical decision to pause game development and rebuild on unified foundations.

## Technical Developments

**Agents Runner Evolution**
We're introducing preflight script support to Agents Runner (currently in planning phase). Repositories containing `Midori-AI-Run.sh` or `auto-run.sh` will execute these scripts as validated preflight checks before agent task execution. This enables repository-specific environment setup while maintaining container security boundaries.

The security layer requires careful design—preflight scripts have full container access by design, so we need robust sandboxing that doesn't break legitimate setup workflows. Luna's researching approaches from similar systems (GitHub Actions, GitLab CI, Docker ENTRYPOINT patterns) before settling on implementation. The challenge: allow scripts to install dependencies and configure environments without creating attack vectors for malicious repositories.

**Repository Structure Standardization**
The Codex Template project is migrating from `.codex` to `.agents` directory naming. The rename matters because names shape how people think about systems—"codex" suggests documentation or knowledge base, while "agents" correctly signals orchestration and automation infrastructure. This reduces namespace confusion with other "codex" projects and makes the directory's purpose immediately clear to new contributors. Existing projects will migrate gradually to maintain compatibility.

**Experimental Hardware Projects**
What if you could run Android apps natively on your phone but control them from your desktop—no emulation, just display remapping?

Luna built a scrcpy-based system that does exactly this. Instead of just mirroring the phone screen to desktop (standard scrcpy behavior), the setup creates a secondary virtual display on the phone, loads apps into that background display, and streams only that content to the desktop. The phone's hardware does all the work natively—better performance for hardware-intensive apps, though you're tied to your physical device's capabilities.

This is Waydroid's concept inverted: Waydroid emulates Android on your Linux desktop to run mobile apps locally. Luna's approach runs apps on actual phone hardware and projects the interface to desktop, avoiding emulation overhead entirely while maintaining native phone performance characteristics. Whether this becomes a published tool or stays a personal workflow experiment depends on whether the performance benefits and use cases justify packaging it for broader use.

## Product Strategy: Game Ecosystem Rethinking

We're pausing active development on both Endless-Autofighter and Endless-Idler to reassess architectural foundations. This is the most significant decision this week.

**The Problem:** Both games work individually, but they don't share infrastructure. Combat systems diverge, progression models clash, and adding features means implementing them twice.

**What's Divergent:**

• **Combat:** Autofighter uses frame-by-frame animation-driven collision detection; Idler uses turn-based stat blocks and damage formulas. No shared combat code, no reusable damage calculations, no unified particle effects.

• **Progression:** Autofighter gates content behind player skill (dodge timing, positioning); Idler gates content behind idle time accumulation and prestige. When Luna prototyped a hybrid system, she had to maintain two separate progression trackers with incompatible save formats.

• **UI Architecture:** Autofighter uses canvas-based rendering for real-time visuals; Idler uses DOM-based menus and stat displays. Result: no shared UI components, no unified styling, duplicated menu patterns across both codebases.

• **Asset Pipeline:** Autofighter expects sprite sheets with specific naming conventions; Idler uses static images and icon fonts. Luna spent hours last week trying to reuse a particle effect—the games have incompatible asset loading systems.

**The Solution:** Luna's stepping back to design a cohesive game ecosystem. The plan:

1. Build a shared game engine core with modular combat systems (turn-based and real-time as plugins)
2. Standardize progression mechanics with a unified save format that supports both idle and active play patterns
3. Create a component library for UI that works across both game types
4. Implement a consistent asset pipeline that handles sprites, static images, animations, and effects uniformly

This pause represents disciplined product management—building on weak foundations creates compounding technical debt. Better to invest time now in proper architecture than maintain multiple incompatible systems that can't learn from each other. The games will be unavailable during reconstruction, but the foundation will support faster feature development, shared improvements, and eventually more games in the ecosystem.

Luna estimates 2-3 weeks for the core infrastructure work before bringing Endless-Autofighter and Endless-Idler back online with unified foundations.

**Read the full technical update at blog.midori-ai.xyz**

—**Becca Kay**  
Midori AI Community Manager
