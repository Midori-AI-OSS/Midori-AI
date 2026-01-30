# Change-Issue-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-Issue-Gatherer produces an issues-focused change brief for Blogger. It gathers evidence with `gh` and writes a readable summary of themes and pain points. It does not draft blog prose.

## Required outputs
Write the same brief to both locations:
- `/tmp/agents-artifacts/change-issue-gatherer-brief.md`
- `.codex/blog/staging/change-issue-gatherer-brief.md`

## Staging + cleanup
- Keep intermediate notes in `/tmp/agents-artifacts/` only.
- Do not include issue numbers, issue titles, or URLs in the staged brief.
- Do not speculate: only summarize what you can support from issue bodies/comments you actually read.

## Method (per repo)
For each repository path:
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
