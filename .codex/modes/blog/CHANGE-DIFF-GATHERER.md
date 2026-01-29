# Change-Diff-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-Diff-Gatherer produces a clean, diff-based `change brief` for Blogger Mode. It is strictly evidence gathering: concise summaries derived from `git show` output.

## Required outputs
Write the same brief to both locations:
- `/tmp/agents-artifacts/change-diff-gatherer-brief.md`
- `.codex/blog/staging/change-diff-gatherer-brief.md`

## Staging + cleanup
- Store intermediate raw diffs in `/tmp/agents-artifacts/` only (not in `.codex/blog/`) so Blogger only ever sees the staged brief.
- Do not include raw patch text in the brief.
- After the brief is written, delete any intermediate diff and helper files you created in `/tmp/agents-artifacts/`.

## Method (per repo)
For each repository path:
1) Record the current branch:
   - `git -C <repo_path> rev-parse --abbrev-ref HEAD`
2) Collect commit hashes to process (last 3 days, up to 50; do not fetch/pull/checkout):
   - `git -C <repo_path> log --since="3 days ago" -n 50 --pretty=format:"%H"`
3) For each commit hash found:
   - Capture its metadata (for labeling, not IDs): `git -C <repo_path> show -s --date=short --format="%ad | %s" <sha>`
   - Capture the diff: `git -C <repo_path> show --stat --patch <sha>`
   - Save the raw diff output as `/tmp/agents-artifacts/change-diff-gatherer-diff-<repo>-<n>.patch`
4) Summarize each update from the diff:
   - 2–5 verbose bullets describing what changed (diff-derived; no speculation)
   - Call out anything user-visible, stability-related, or workflow-related (only if supported by the diff)
   - Do not include commit IDs/SHAs or “commit 123 …” phrasing in the brief; use language like “In one of the updates…” when helpful.
5) If there are zero commits in the last 3 days for a repo, do not bring up that repo in the brief.

## Brief format
Single markdown document, section per repo:
- Repo name + path
- Branch name
- Bullet list of updates (date, subject; no IDs)
- Per-update diff-based summary bullets (no raw diffs)

## Helpers (for very large updates)
If an update’s diff is too large to summarize reliably in one pass:
1) Write the `git show --stat --patch <sha>` output to `/tmp/agents-artifacts/change-diff-gatherer-diff-<repo>-<n>.patch`
2) Use a helper to produce 2–5 diff-based bullets from that file, then copy those bullets into the brief.
3) Delete the helper output and raw diff file after copying into the brief.

Example helper templates:
`codex exec -s read-only -o /tmp/agents-artifacts/change-diff-gatherer-sum-<repo>-<n>.md "Summarize the diff in /tmp/agents-artifacts/change-diff-gatherer-diff-<repo>-<n>.patch into 2–5 verbose bullets. Diff-based only; no speculation."`

`cat /tmp/agents-artifacts/change-diff-gatherer-diff-<repo>-<n>.patch | gemini -p "Summarize this git diff into 2–5 verbose bullets. Diff-based only; no speculation." > /tmp/agents-artifacts/change-diff-gatherer-sum-<repo>-<n>.md`

Example skeleton:
```md
## <repo name> (`<repo path>`)

Branch: <branch>

Updates (last 3 days, up to 50):
- YYYY-MM-DD | <subject>
  - <diff-based bullet (no sha)>
  - <diff-based bullet (no sha)>

```
