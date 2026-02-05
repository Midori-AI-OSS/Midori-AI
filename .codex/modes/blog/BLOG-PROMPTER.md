# Blog-Prompter Mode (Handoff Builder)

## Purpose
Blog-Prompter combines the outputs of the change gatherer modes into a single, Blogger-ready handoff. It does not gather new evidence (no `git log`, no `git show`, no `gh`).

## Inputs
Read these files if present (prefer `/tmp/agents-artifacts/`, fall back to `.codex/blog/staging/`):
- `/tmp/agents-artifacts/change-diff-gatherer-brief.md`
- `.codex/blog/staging/change-diff-gatherer-brief.md`
- `/tmp/agents-artifacts/change-pr-gatherer-brief.md`
- `.codex/blog/staging/change-pr-gatherer-brief.md`
- `/tmp/agents-artifacts/change-issue-gatherer-brief.md`
- `.codex/blog/staging/change-issue-gatherer-brief.md`
- `/tmp/agents-artifacts/change-context-gatherer-brief.md`
- `.codex/blog/staging/change-context-gatherer-brief.md`

## Required outputs
Write the combined handoff to:
- `/tmp/agents-artifacts/blogger-handoff.md`

Optional staging (only if the Coordinator explicitly requests it):
- `.codex/blog/staging/blogger-handoff.md`

## Guardrails (critical)
- Do not delete or modify input brief files (staged or in `/tmp/agents-artifacts/`). Cross-agent cleanup is handled by `CLEANUP` mode.
- Prefer writing outputs to `/tmp/agents-artifacts/` only to avoid dirtying the workspace git status and to prevent cross-agent collisions.

## Handoff writing rules
- Do not add new facts.
- Keep the handoff easy to skim: short sections, verbose bullets.
- Do not include IDs that trigger “123 added X” writing:
  - No commit SHAs, PR numbers, issue numbers, URLs.
  - Prefer phrasing like “In one of the updates…” / “Recent changes include…”.
- If an input file is missing, omit that section; do not guess.

## Suggested handoff structure
```md
# Blogger Handoff

## High-level themes
- ...

## Repo-by-repo
### <repo>
- ...

## User-visible / stability / workflow highlights
- ...

## What went sideways (only if evidenced)
- ...
```
