# Repository Contributor Guide

This document summarizes common development practices for all services in this repository.

---


## Where to Look for Guidance (Per-Service Layout)
- **`.feedback/`**: Task lists and priorities. *Read only*—never edit directly.
- **`.codex/`** (inside each service directory, e.g., `WebUI/.codex/`, `Rest-Servers/.codex/`):
  - Use it for contributor coordination (tasks, modes, notes). Prefer reading code and docstrings as the source of truth; keep notes minimal and task-scoped.
- **`.github/`**: Workflow guidelines and UX standards.

---

## Development Basics
- Use [`uv`](https://github.com/astral-sh/uv) for Python environments and running code. Avoid `python` or `pip` directly.
- Use [`bun`](https://bun.sh/) for Node/React tooling instead of `npm` or `yarn`.
- Verification-first: confirm current behavior in the codebase before changing code; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.
- No broad fallbacks: do not add “fallback behavior everywhere”; only add a narrow fallback when the task explicitly requires it, and justify it.
- No backward compatibility shims by default: do not preserve old code paths “just in case”; only add compatibility layers when the task explicitly requires it.
- Minimal documentation, minimal logging: prefer reading code and docstrings; do not add docs/logs unless required to diagnose a specific issue or prevent a crash.
- Do not update `README.md`.
- Split large modules into smaller ones when practical.
- Commit frequently with messages formatted `[TYPE] Title`; pull requests use the same format and include a short summary.
- If a build retry occurs, the workflow may produce a commit titled `"Applying previous commit."` when reapplying a patch.
  This is normal and does not replace the need for your own clear `[TYPE]` commit messages.
- Run available tests (e.g., `pytest`) before committing.
- Any test running longer than 25 seconds is automatically aborted.
- For Python style:
   - Place each import on its own line.
   - Sort imports within each group (standard library, third-party, project modules) from shortest to longest.
   - Insert a blank line between each import grouping (standard library, third-party, project modules).
   - Avoid inline imports.
   - For `from ... import ...` statements, group them after all `import ...` statements, and format each on its own line, sorted shortest to longest, with a blank line before the group. Example:

     ```python
     import os
     import time
     import logging
     import threading

     from datetime import datetime
     from rich.console import Console
     from langchain_text_splitters import RecursiveCharacterTextSplitter
     ```

---

## Contributor Modes
The repository supports several contributor modes to clarify expectations and best practices for different types of contributions:

**All contributors should regularly review and keep their mode cheat sheet in `.codex/notes/` up to date.**
Refer to your mode's cheat sheet for quick reminders and update it as needed.

- **Task Master Mode** (`.codex/modes/TASKMASTER.md`): For creating, organizing, and maintaining actionable tasks in the root `.codex/tasks/` folder. Task Masters define and prioritize work for Coders and ensure tasks are ready for implementation.
- **Manager Mode** (`.codex/modes/MANAGER.md`): For planning, coordination, and maintaining contributor guidance across the monorepo. Managers steward `AGENTS.md`, mode docs, and process alignment with Task Masters and stakeholders.
- **Coder Mode** (`.codex/modes/CODER.md`): For implementing, refactoring, and reviewing code. Focuses on high-quality, maintainable, and well-documented contributions. Coders regularly review the `.codex/tasks/` folder for new or assigned work.
- **Reviewer Mode** (`.codex/modes/REVIEWER.md`): For auditing repository documentation and filing `TMT`-prefixed tasks when updates are needed.
- **Auditor Mode** (`.codex/modes/AUDITOR.md`): For performing comprehensive reviews and audits. Emphasizes thoroughness, completeness, and catching anything others may have missed.
- **Blogger Mode** (`.codex/modes/BLOGGER.md`): For creating, publishing, and managing blog posts. Bloggers use shell scripts (see `.codex/blog/scripts/post_blog.sh`) to simulate posting (echo a message). Keep drafts for human posting; before generating a new batch, archive/move old drafts out of the active folder so only the current batch is queued. Bloggers should keep their cheat sheet in `.codex/notes/` up to date.
- **Brainstormer Mode** (`.codex/modes/BRAINSTORMER.md`): For collaborative idea generation and capturing options for future tasks.
- **Prompter Mode** (`.codex/modes/PROMPTER.md`): For crafting high-quality prompts for LLM/LRM interactions.
- **Unknown Mode** (no file): If you are unsure which mode applies or are asked to perform an action outside your capabilities—such as creating a task while in read-only mode—review the guides in `.codex/modes/`, choose the closest fit, and use the team communication command (`contact.sh`) to clarify the situation. This helps us improve our prompting and documentation for future contributors.

Refer to the relevant mode guide in `.codex/modes/` before starting work. For service-specific details, read the service's own `AGENTS.md` and follow existing in-repo guidance.
