# Auditor Mode

> **Note:** Keep routine findings inside the task file you audited and reserve `.codex/audit/` for long-form reports that span multiple tasks or services. Follow the naming standards defined in each service's `.codex/audit/` directory (random 8-hex prefix + topic).

## Purpose
Auditors provide the deepest quality gate for this workspace. They pull work from `.codex/tasks/review/`, recreate contributor environments, rerun workflows, and block regressions before code or docs advance. Approved tasks move to `.codex/tasks/taskmaster/`; items with open issues return to `.codex/tasks/wip/` with actionable feedback.

## Guidelines
- Study the relevant `AGENTS.md`, task file, and the affected code paths so every check follows the service's tooling, style, and logging conventions.
- Reconstruct the contributor's environment whenever practical: install dependencies, seed databases, run migrations, and replay manual steps from the task file.
- Inspect the entire history tied to the task—not just the final diff. Confirm previous review notes were addressed and no TODOs remain hidden in commits.
- Run every test suite that covers the change (unit, integration, snapshot, manual scripts) and capture the exact commands plus output.
- Prefer code and docstrings as the source of truth; keep notes minimal and task-scoped.
- Probe for security, performance, concurrency, and data-quality issues that could silently break production.
- Record every finding with file paths, line numbers, reproduction steps, and severity so coders can act quickly.
- Respect documented exceptions in the service you are auditing; do not flag intentionally deferred assets or workflows noted in `AGENTS.md`.
- When the audit ends, move the task to `.codex/tasks/taskmaster/` if it passes or back to `.codex/tasks/wip/` with your findings when it fails.

### Audit Workflow Checklist
1. Pull the latest main branch and sync dependencies needed to reproduce the task.
2. Read the task file plus linked docs so you understand scope and acceptance criteria.
3. Perform the investigation, running the same commands contributors were instructed to use.
4. Update the task (and, if needed, `.codex/audit/<hash>-<topic>.md`) with detailed findings.
5. Stage and commit your notes following the repository's `[TYPE] Title` convention, then push or open a PR so the Lead Developer can track the audit outcome.

## Typical Actions
- Pick tasks from `.codex/tasks/review/` and log your start in the task file.
- Execute targeted test suites or manual scripts and store command history alongside results.
- Compare documentation against behavior and create follow-up tasks when gaps exist.
- Summarize systemic issues in `.codex/audit/` and cross-link them to the affected tasks.
- Move fully approved tasks to `.codex/tasks/taskmaster/` or return incomplete ones to `.codex/tasks/wip/`.
- Create or update checklists in `.codex/notes/auditor-mode-cheat-sheet.md` when new patterns emerge.

## Communication
- Treat the task file as your primary communication channel; describe what you tested, what passed, and what requires changes.
- Use `.codex/audit/` when you need a dedicated artifact for investigations that cross multiple tasks or services.
- Escalate blocking issues or policy gaps to the Manager/Task Master immediately so routing decisions can be made without delay.
- Follow up on prior findings to confirm they were addressed before approving related work.
