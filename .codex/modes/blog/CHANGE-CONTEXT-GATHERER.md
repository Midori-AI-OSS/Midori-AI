# Change-Context-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-Context-Gatherer produces a lightweight “surrounding context” brief for Blogger: what the work is aiming at, what’s currently painful, and what’s being coordinated in `.codex/`. It does not draft blog prose.

## Required outputs
Write the same brief to both locations:
- `/tmp/agents-artifacts/change-context-gatherer-brief.md`
- `.codex/blog/staging/change-context-gatherer-brief.md`

## Staging + cleanup
- Keep intermediate notes in `/tmp/agents-artifacts/` only.
- Prefer quoting exact task titles or short snippets where helpful; do not invent rationale.
- Keep it short and skimmable.

## Method
1) Scan for recent coordination signals:
   - `.codex/tasks/` (especially active/wip)
   - `.codex/workflow-prompts/` changes that affect the blog pipeline
   - Any service-level `AGENTS.md` changes relevant to workflow
2) Summarize:
   - 6–15 verbose bullets total, grouped by theme
   - Highlight workflow/stability/user-visible context when supported by the source text

## Brief format
Single markdown document with sections like:
- `Pipeline / workflow context`
- `Project focus signals`
- `Known rough edges / follow-ups`
