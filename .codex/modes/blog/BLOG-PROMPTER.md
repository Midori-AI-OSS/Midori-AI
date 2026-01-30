# Blog-Prompter Mode (Handoff Builder)

## Purpose
Blog-Prompter combines the outputs of the change gatherer modes into a single, Blogger-ready handoff. It does not gather new evidence (no `git log`, no `git show`, no `gh`).

## Inputs (staging)
Reads these files if present:
- `.codex/blog/staging/change-diff-gatherer-brief.md`
- `.codex/blog/staging/change-pr-gatherer-brief.md`
- `.codex/blog/staging/change-issue-gatherer-brief.md`
- `.codex/blog/staging/change-context-gatherer-brief.md`

## Required outputs
Write the combined handoff to both locations:
- `/tmp/agents-artifacts/blogger-handoff.md`
- `.codex/blog/staging/blogger-handoff.md`

## Cleanup (required)
After `blogger-handoff.md` is written to both targets, delete the source brief files from `.codex/blog/staging/`:
- `.codex/blog/staging/change-diff-gatherer-brief.md`
- `.codex/blog/staging/change-pr-gatherer-brief.md`
- `.codex/blog/staging/change-issue-gatherer-brief.md`
- `.codex/blog/staging/change-context-gatherer-brief.md`

Example cleanup commands (only after confirming the handoff exists):
`rm -f .codex/blog/staging/change-diff-gatherer-brief.md .codex/blog/staging/change-pr-gatherer-brief.md .codex/blog/staging/change-issue-gatherer-brief.md .codex/blog/staging/change-context-gatherer-brief.md`

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
