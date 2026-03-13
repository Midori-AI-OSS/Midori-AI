# How to Get Each Subrepo's Git Commits and PRs (README-based Workflow)

This guide explains how to manually collect commit logs and pull request context from all git repositories in the mono-repo, using the main `README.md` as the source of truth for which repos/services to include.

## Step 0: Set the Baseline (Last Website Post)

Use the newest filename in `./Website-Blog/blog/posts/` (`YYYY-MM-DD.md`) as the baseline date for “since last post”.

## Step 1: Extract Repo Links from the Main README

1. Open the main `README.md` in the project root.
2. Identify all links to subrepos/services. These are typically markdown links to subfolders (e.g., `[Endless-Autofighter](Endless-Autofighter/)`).
3. Copy the relative paths for each linked repo/service.

*Tip: To extract all markdown links to subfolders, you can use a command like:*

```bash
grep -oP '\[.*?\]\(([^)]+/)\)' README.md | sed -E 's/.*\(([^)]+)\).*/\1/'
```

## Step 2: Get the Last 10 Commits from Each Repo

For each repo/service path you found in Step 1:

```bash
cd <repo-folder>
git log -n 10 --pretty=format:"%h %ad %s" --date=short
cd -
```

Replace `<repo-folder>` with the path from the README link (e.g., `Endless-Autofighter`).

## Step 3: Collect PR Context with `gh` (Per Repo)

Inside each repo folder (so the correct GitHub remote is used), collect:

- **Current open PRs**
- **PRs opened since the baseline date**
- **PRs closed since the baseline date**

Example commands (adjust `YYYY-MM-DD`):

```bash
cd <repo-folder>
gh pr list --state open --limit 50
gh pr list --state all --search "created:>=YYYY-MM-DD" --limit 50
gh pr list --state closed --search "closed:>=YYYY-MM-DD" --limit 50
cd -
```

If `gh` is missing or not authenticated for a repo, do not invent PRs; record that PR listing was unavailable and proceed with commit-based reporting.

## Step 4: Save or Organize the Output

You can redirect the output to a file for each repo:

```bash
cd <repo-folder>
git log -n 10 --pretty=format:"%h %ad %s" --date=short > ../<repo-folder>_commits.txt
cd -
```

Organize files as needed (e.g., by date or repo).

## Step 5: Troubleshooting & Tips

- **Missing Repos:** If a repo/service is missing from your commit logs, check that it is properly linked in the main `README.md`.
- **Permissions:** Make sure you have read access to all folders.
- **Malformed Links:** Ensure the README links point to actual repo directories.

----

This guide should help you manually collect commit logs from all subrepos/services in your project tree, using the main `README.md` as your source of truth.
