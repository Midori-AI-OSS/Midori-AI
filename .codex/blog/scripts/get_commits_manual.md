# How to Get Each Subrepo's Git Commits (README-based Workflow)

This guide explains how to manually collect commit logs from all git repositories in the mono-repo, using the main `README.md` as the source of truth for which repos/services to include.

## Step 1: Extract Repo Links from the Main README

1. Open the main `README.md` in the project root.
2. Identify all links to subrepos/services. These are typically markdown links to subfolders (e.g., `[Lyra-Project](AGI/Lyra-Project/)`).
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

Replace `<repo-folder>` with the path from the README link (e.g., `AGI/Lyra-Project`).

## Step 3: Save or Organize the Output

You can redirect the output to a file for each repo:

```bash
cd <repo-folder>
git log -n 10 --pretty=format:"%h %ad %s" --date=short > ../<repo-folder>_commits.txt
cd -
```

Organize files as needed (e.g., by date or repo).

## Step 4: Troubleshooting & Tips

- **Missing Repos:** If a repo/service is missing from your commit logs, check that it is properly linked in the main `README.md`.
- **Permissions:** Make sure you have read access to all folders.
- **Malformed Links:** Ensure the README links point to actual repo directories.

----

This guide should help you manually collect commit logs from all subrepos/services in your project tree, using the main `README.md` as your source of truth.
