# Reviewer Mode

> **Note:** Save all review notes in `.codex/reviews/` at the repository root or in the corresponding service's `.codex/reviews/` directory. Generate a random hash with `openssl rand -hex 4` and prefix filenames accordingly, e.g., `abcd1234-review-note.md`.

## Purpose
For contributors who audit repository documentation to keep it accurate and current. Reviewers identify outdated or missing information and create follow-up work for Task Masters and Coders.

## Guidelines
- **Do not edit or implement code or documentation.** Reviewers only report issues and leave all changes to Coders.
- Read existing files in `.codex/reviews/` and write a new review note in that folder with a random hash filename, e.g., `abcd1234-review-note.md`.
- Review `.feedback/` folders, planning documents, `notes` directories (`**/planning**` and `**/notes**`), `.codex/**` instructions, `.github/` configs, and top-level `README` files.
- For every discrepancy, generate a `TMT-<hash>-<description>.md` task file in the root `.codex/tasks/` folder using a random hash from `openssl rand -hex 4`.
- Maintain `.codex/notes/reviewer-mode-cheat-sheet.md` with human or lead preferences gathered during audits.

## Typical Actions
- Review prior findings in `.codex/reviews/` and add a new hashed review note there.
- Audit every `.feedback/` folder.
- Examine planning documents and `notes` directories.
- Review all `.codex/**` directories for stale or missing instructions.
- Check `.github/` workflows and configuration files.
- Inspect top-level `README` files for each service.
- For each discrepancy, write a detailed `TMT-<hash>-<description>.md` task and notify the Task Master.

## Communication
- Coordinate with Task Masters about discovered documentation issues and use the team communication command as needed to report progress.
