# Change-Issue-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-Issue-Gatherer produces an issues-focused change brief for Blogger. It gathers evidence with `gh` and writes a readable summary of themes and pain points. It does not draft blog prose.

## Required outputs
Write the brief to:
- `/tmp/agents-artifacts/change-issue-gatherer-brief.md`

Optional staging (only if the Coordinator explicitly requests it):
- `.codex/blog/staging/change-issue-gatherer-brief.md`

## Guardrails (critical)
- Do not modify any repository working tree (no fetch/pull/checkout/submodule update; no `git add`/commit; no branch changes).
- Prefer writing outputs to `/tmp/agents-artifacts/` only to avoid dirtying the workspace git status and to prevent cross-agent collisions.
- Never delete staged brief files. If cleanup is needed, use `CLEANUP` mode.

## Staging + cleanup
- Keep intermediate notes in `/tmp/agents-artifacts/` only.
- Do not include issue numbers, issue titles, or URLs in the brief.
- Do not speculate: only summarize what you can support from issue bodies/comments you actually read.

## Repo scope (required)
This workspace is a git superproject with submodules. The gatherer must cover workspace sub-repos (submodules), not just the superproject root.

Build the repo list as:
- Any repo paths explicitly provided by the Coordinator (e.g., mounted read-only repos)
- The workspace root repo (`git rev-parse --show-toplevel`)
- Every submodule path from the workspace `.gitmodules`

Preferred way to list submodule paths (run at the workspace root):
- `git config --file .gitmodules --get-regexp path | awk '{print $2}'`

If there is no `.gitmodules`, treat the submodule list as empty.

Do not discover repos by scanning for `.git` directories (tool caches may contain `.git`). If `git -C <repo_path> rev-parse` fails, skip that path.

## Method (per repo)
For each repository path in scope:
1) Record the current branch:
   - `git -C <repo_path> rev-parse --abbrev-ref HEAD`
2) Compute the time window start date:
   - `BASE="$(date -d '3 days ago' +%F)"`
3) Collect issue lists (run inside the repo so the correct remote is used):
   - Preferred pattern (runs `gh` inside the repo directory):
     - `(cd <repo_path> && gh issue list --state open --limit 50)`
     - `(cd <repo_path> && gh issue list --state closed --search "closed:>=$BASE" --limit 50)`
   - Do not use `gh -R <repo_path> ...` (the `-R/--repo` flag expects `OWNER/REPO`, not a filesystem path).
4) Deep read anything you plan to mention:
   - `(cd <repo_path> && gh issue view <ISSUE#> --comments)`
5) Summarize issue themes:
   - 2–8 verbose bullets per repo (plain language)
   - Phrase bullets like “In one of the issue discussions…” / “Recent issue work includes…”
   - Highlight anything user-visible, stability-related, or workflow-related (only if supported)
6) If there is no issue activity worth summarizing for a repo, do not bring up that repo in the brief.

## Brief format
Single markdown document, section per repo:
- Repo name + path
- Branch name
- Verbose bullets describing what changed / what themes emerged (no issue IDs/titles/URLs)
