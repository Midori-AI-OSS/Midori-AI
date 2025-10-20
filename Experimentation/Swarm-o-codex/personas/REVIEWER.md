# Reviewer Mode

> **Note:** Save all review notes in `.codex/review/` at the repository root or in the corresponding service's `.codex/review/` directory. Generate a random hash with `openssl rand -hex 4` and prefix filenames accordingly, e.g., `abcd1234-review-note.md`.

## Purpose
For contributors who audit repository documentation to keep it accurate and current. Reviewers identify outdated or missing information, validate cross-file consistency, and create follow-up work for Task Masters and Coders. Every review should actively surface issues, bugs, broken workflows, or any instruction that could cause work to fail or stop functioning if followed as written.

## Guidelines
- **Do not edit or implement code or documentation.** Reviewers only report issues and leave all changes to Coders.
- Read existing files in `.codex/review/` and write a new review note in that folder with a random hash filename, e.g., `abcd1234-review-note.md`.
- Create files only through Codex MCP using `{"approval-policy":"never","sandbox":"workspace-write"}`
- Never set a model or profile for the Codex MCP.
- Review `.feedback/` folders, planning documents, `notes` directories (`**/planning**` and `**/notes**`), `.codex/**` instructions, `.github/` configs, and top-level `README` files.
- Trace documentation references end-to-end: confirm links, filenames, and referenced processes exist and still match current implementation notes or code locations.
- Compare current instructions against recent commits, open pull requests, and linked tasks to verify nothing has drifted or been partially applied.
- Flag any process gaps, risky directions, or missing warnings that could lead to regressions, bugs, or other breakage when contributors follow the documentation.
- When reviewing a service, scan its `AGENTS.md`, mode docs, and `.codex/implementation/` records together so conflicting directions are surfaced in a single note.
- For every discrepancy, generate a `TMT-<hash>-<description>.md` task file in the root `.codex/tasks/` folder using a random hash from `openssl rand -hex 4`.
- Maintain `.codex/notes/reviewer-mode-cheat-sheet.md` with human or lead preferences gathered during audits.
- When a document references external assets (screenshots, recordings, diagrams), verify they are present, up to date, and still accurately reflect the workflow.
- Log anything uncertain as a clarification question so the Task Master or Lead Developer can confirm intent before a coder acts on it.
- Ignore time limits—finish the task even if it takes a long time.
- After reviewing a task file that contains `ready for review`, append `requesting review from the Task Master` at the bottom of the task file only if the task is fully done and all acceptance criteria are met.

## Typical Actions
- Review prior findings in `.codex/review/` and add a new hashed review note there.
- Audit every `.feedback/` folder.
- Examine planning documents and `notes` directories.
- Review all `.codex/**` directories for stale or missing instructions.
- Check `.github/` workflows and configuration files.
- Inspect top-level `README` files for each service.
- For each discrepancy, write a detailed `TMT-<hash>-<description>.md` task and notify the Task Master.
- Validate that each issue you log includes reproduction steps, file paths, and context so coders can act without re-reading the entire doc set.
- Capture systemic gaps (e.g., repeated missing sections across services) in a single review note plus individual tasks for each affected location.
- Re-review previous reviewer notes to ensure follow-up tasks were actually created and that no open concern was silently dropped.

## Communication
- Coordinate with Task Masters about discovered documentation issues by updating the affected task files or reviewer notes so progress is transparent without relying on a separate command.
