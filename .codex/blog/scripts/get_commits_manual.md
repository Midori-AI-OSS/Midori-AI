# How to Get Each Subrepo's Git Commits (Step by Step)

This guide explains how to manually collect commit logs from all git repositories and subrepos (including submodules) in a directory tree. It covers both standard git repos and submodules that use `.git` files.

## Step 1: Find All Git Repositories and Subrepos

Open a terminal in your project root and run:

```bash
find . \( -type d -name ".git" -o -type f -name ".git" \)
```

This will list all `.git` directories (normal repos) and `.git` files (submodules/worktrees).

## Step 2: Determine the Git Directory for Each Repo

- If the result is a **directory** (e.g., `./myrepo/.git`), use it directly.
- If the result is a **file** (e.g., `./submodule/.git`), open it and look for a line like:
  
  ```
  gitdir: ../.git/modules/submodule
  ```
  
  The path after `gitdir:` is the actual git directory. If it's a relative path, resolve it relative to the subrepo's folder.

## Step 3: Get the Commit Logs

For each repo or subrepo, run:

```bash
git --git-dir="<path-to-gitdir>" --work-tree="<repo-folder>" log -n 100 --pretty=format:"%h %ad %s" --date=short
```

Replace `<path-to-gitdir>` and `<repo-folder>` with the correct paths from Step 2.

To filter for today's commits (replace YYYY-MM-DD with the date):

```bash
git --git-dir="<path-to-gitdir>" --work-tree="<repo-folder>" log --since=YYYY-MM-DD --until=YYYY-MM-DD --pretty=format:"%h %ad %s" --date=short
```

## Step 4: Save or Organize the Output

You can redirect the output to a file:

```bash
git ... > myrepo_commits.txt
```

Organize files as needed (e.g., by date or repo).

## Step 5: Troubleshooting & Tips

- **Submodules:** If you see a `.git` file, always check its contents for the real gitdir.
- **Permissions:** Make sure you have read access to all folders.
- **Relative Paths:** When resolving `gitdir:` paths, use the subrepo's folder as the base.
- **Automation:** You can script these steps (see the original `get_commits.sh` for an example).

---

### GUI Alternative

You can also use a git GUI (like GitKraken, SourceTree, or VS Code's git integration) to browse commit logs for each repo and subrepo.

---

This guide should help you manually collect commit logs from all subrepos in your project tree.
