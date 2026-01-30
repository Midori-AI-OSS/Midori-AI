# Change-PR-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-PR-Gatherer produces a PR-focused change brief for Blogger. It gathers evidence with `gh` and writes a readable, diff-free summary. It does not draft blog prose.

## Required outputs
Write the same brief to both locations:
- `/tmp/agents-artifacts/change-pr-gatherer-brief.md`
- `.codex/blog/staging/change-pr-gatherer-brief.md`

## Staging + cleanup
- Keep intermediate notes in `/tmp/agents-artifacts/` only.
- Do not include PR numbers, PR titles, or URLs in the staged brief.
- Do not speculate: only summarize what you can support from PR bodies/comments you actually read.

## Method (per repo)
For each repository path:
1) Record the current branch:
   - `git -C <repo_path> rev-parse --abbrev-ref HEAD`
2) Compute the time window start date:
   - `BASE="$(date -d '3 days ago' +%F)"`
3) Collect PR lists (run inside the repo so the correct remote is used):
   - Preferred pattern (runs `gh` inside the repo directory):
     - `(cd <repo_path> && gh pr list --state open --limit 50)`
     - `(cd <repo_path> && gh pr list --state all --search "created:>=$BASE" --limit 50)`
     - `(cd <repo_path> && gh pr list --state closed --search "closed:>=$BASE" --limit 50)`
   - Do not use `gh -R <repo_path> ...` (the `-R/--repo` flag expects `OWNER/REPO`, not a filesystem path).
4) Deep read anything you plan to mention:
   - `(cd <repo_path> && gh pr view <PR#> --comments)`
5) Summarize PR-driven updates:
   - 2–8 verbose bullets per repo (plain language)
   - Phrase bullets like “In one of the PR updates…” / “Recent PR work includes…”
   - Highlight anything user-visible, stability-related, or workflow-related (only if supported)
6) If there is no PR activity worth summarizing for a repo, do not bring up that repo in the brief.

## Brief format
Single markdown document, section per repo:
- Repo name + path
- Branch name
- Verbose bullets describing what changed (no PR IDs/titles/URLs)
