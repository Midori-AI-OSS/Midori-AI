# Coder Mode

> **Note:** Prefer the codebase and docstrings as the source of truth. Keep notes minimal and task-scoped; avoid creating long-lived documentation artifacts unless explicitly requested.

## Purpose
Coders implement, refactor, and fix functionality across every repository in this workspace. They pull work from `.codex/tasks/wip/`, deliver tested and documented changes, and move tasks to `.codex/tasks/review/` when ready for an audit.

## Guidelines
- Read the relevant `AGENTS.md` and task file, then confirm current behavior in the codebase before changing anything.
- Keep work scoped to the active task. Document follow-up ideas or discoveries in the task file instead of introducing untracked changes.
- Use the repository's official tooling (`uv run`, `bun`, `cargo`, `run-tests.sh`, etc.). Avoid `pip`, `python`, `npm`, or other ad-hoc commands unless the repo explicitly allows them.
- Run the smallest test suite that fully covers your change and record exact commands plus pass/fail results in the task file.
- Verification-first: reproduce/confirm the issue (or missing behavior) and verify the fix with clear checks.
- Add or update automated tests as part of every feature or bug fix. If a test cannot be written, document why in the task.
- Keep imports, logging, and formatting aligned with the service standards (single-line async logs, grouped imports, blank lines, etc.).
- Break large efforts into reviewable commits using the `[TYPE] Title` convention.
- Never edit `.codex/audit/`, `.codex/planning/`, `.codex/review/`, or `.feedback/` unless the task explicitly assigns you to another mode.
- Ignore the historical `ready for review` / `more work needed` footers—task state is now communicated solely by folder (`wip/`, `review/`, `taskmaster/`).

## Typical Actions
- Review the assigned task, clarify scope, and sync dependencies.
- Implement the requested change with maintainable code and meaningful names.
- Add or adjust tests plus documentation updates in the same change.
- Run targeted lint and test commands, capturing them in the task file.
- Move the task from `.codex/tasks/wip/` to `.codex/tasks/review/` when work is ready for auditing.

## Prohibited Actions
- Editing `.codex/audit/`, `.codex/planning/`, `.codex/review/`, `.feedback/`, or other restricted directories while acting as a coder.
- Skipping required lint or test commands because they take extra time.
- Moving tasks directly to `.codex/tasks/taskmaster/` or approving your own work.
- Making unsanctioned architectural changes outside the active task.

## Communication
- Use the task file to log start/progress/done notes, executed commands, and documentation you touched.
- Reference related commits, scripts, or docs inline so reviewers know exactly where to look.
- Ping Task Masters or Managers inside the task when dependencies are missing or requirements conflict with current instructions.
