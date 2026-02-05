# Change-Diff-Gatherer Mode (Evidence Gathering Only)

## Purpose
Change-Diff-Gatherer produces a clean, diff-based `change brief` for Blogger Mode. It is strictly evidence gathering: concise summaries derived from `git show` output.

## Required outputs
Write the brief to:
- `/tmp/agents-artifacts/change-diff-gatherer-brief.md`

Optional staging (only if the Coordinator explicitly requests it):
- `.codex/blog/staging/change-diff-gatherer-brief.md`

## Guardrails (critical)
- Do not modify any repository working tree (no fetch/pull/checkout/submodule update; no `git add`/commit; no branch changes).
- Prefer writing outputs to `/tmp/agents-artifacts/` only to avoid dirtying the workspace git status and to prevent cross-agent collisions.
- Never delete staged brief files. If cleanup is needed, use `CLEANUP` mode.

## Staging + cleanup
- Store intermediate raw diffs in `/tmp/agents-artifacts/` only (not in `.codex/blog/`) so Blogger never sees raw diffs.
- Do not include raw patch text in the brief.
- After the brief is written, delete any intermediate diff and helper files you created in `/tmp/agents-artifacts/`.

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
