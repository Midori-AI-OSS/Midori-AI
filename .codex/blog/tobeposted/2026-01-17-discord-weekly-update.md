# Weekly Update: Polishing the Edges 🎨

Hey everyone! Becca here with your weekly snapshot of what's been happening across our projects.

## Agent-Runner Gets a Facelift

Our Agent-Runner tooling got some serious love this week. We vendored Lucide icons for consistent, crisp HiDPI rendering across all platforms—no more blurry buttons! The Task Details layout also got a complete refactor: logs on the left, details on the right. Much cleaner for debugging. We also fixed some critical bugs around GitHub Context token forwarding and cross-agent delegation.

Behind the scenes, we split template prompting into modular markdown files and added an out-of-process Desktop viewer for noVNC to prevent GUI crashes. Plus, Docker validation now happens on first-run setup so you know immediately if something's misconfigured.

## Endless-Idler: New Prestige System & Combat Polish

The big news for Endless-Idler is the **prestige system** is live! Players can now rebirth with meaningful progression—reset your run but keep permanent bonuses for future attempts. This is the long-term progression system players have been asking for.

We also rolled out some seriously cool visual improvements:

- **Wrong-way healing arrows** with Bezier curves and midpoint behavior—when an enemy heals an ally, you now see a beautiful curved arrow pointing backward. Makes combat way more readable.
- **Unified crit mod system** replacing the old separate crit rate/crit damage stats. One stat to rule them all, much cleaner balance.
- **Glass morphism tooltips** for that sleek, modern, semi-transparent look throughout the UI
- Bug fixes including the Trinity Synergy infinite stacking exploit and arrow drawing crashes that were affecting some players

Behind the scenes, we cleaned up a massive amount of task files (shoutout to our Auditors!) and removed obsolete docs to keep the repo focused and maintainable.

## Docs Everywhere

Almost every repo got documentation updates this week. AGENTS.md, CODER.md, AUDITOR.md, TASKMASTER.md—all revised for clarity and consistency. The Midori-AI-Website also added comprehensive Docker and UV setup guides for Ubuntu, Fedora, and Arch flavors.

---

That's the week! Questions? Hit Luna up in the Discord.

—Becca 💜
