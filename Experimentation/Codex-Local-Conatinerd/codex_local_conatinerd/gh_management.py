import os
import re
import shutil
import subprocess
import time

from dataclasses import dataclass


class GhManagementError(RuntimeError):
    pass


def is_gh_available() -> bool:
    return shutil.which("gh") is not None


@dataclass(frozen=True, slots=True)
class RepoPlan:
    workdir: str
    repo_root: str
    base_branch: str
    branch: str


def _run(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout_s: float = 45.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise GhManagementError(f"command timed out: {' '.join(args)}") from exc
    except OSError as exc:
        raise GhManagementError(f"command failed: {' '.join(args)}") from exc


def _require_ok(proc: subprocess.CompletedProcess[str], *, args: list[str]) -> None:
    if proc.returncode == 0:
        return
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    extra = stderr or stdout
    if extra:
        raise GhManagementError(f"command failed ({proc.returncode}): {' '.join(args)}\n{extra}")
    raise GhManagementError(f"command failed ({proc.returncode}): {' '.join(args)}")


def _expand_dir(path: str) -> str:
    return os.path.abspath(os.path.expanduser((path or "").strip()))


def is_git_repo(path: str) -> bool:
    path = _expand_dir(path)
    if not os.path.isdir(path):
        return False
    proc = _run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"], timeout_s=8.0)
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


def git_repo_root(path: str) -> str | None:
    path = _expand_dir(path)
    if not os.path.isdir(path):
        return None
    proc = _run(["git", "-C", path, "rev-parse", "--show-toplevel"], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    root = (proc.stdout or "").strip()
    return root if root else None


def git_current_branch(repo_root: str) -> str | None:
    repo_root = _expand_dir(repo_root)
    proc = _run(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    branch = (proc.stdout or "").strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def git_default_base_branch(repo_root: str) -> str | None:
    repo_root = _expand_dir(repo_root)
    proc = _run(
        ["git", "-C", repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        timeout_s=8.0,
    )
    if proc.returncode != 0:
        return None
    ref = (proc.stdout or "").strip()
    if not ref.startswith("origin/"):
        return None
    branch = ref.removeprefix("origin/").strip()
    return branch or None


def git_is_clean(repo_root: str) -> bool:
    repo_root = _expand_dir(repo_root)
    proc = _run(["git", "-C", repo_root, "status", "--porcelain"], timeout_s=15.0)
    if proc.returncode != 0:
        return False
    return not (proc.stdout or "").strip()


def _is_empty_dir(path: str) -> bool:
    try:
        return os.path.isdir(path) and not os.listdir(path)
    except OSError:
        return False


def ensure_github_clone(
    repo: str,
    dest_dir: str,
    *,
    prefer_gh: bool = True,
    recreate_if_needed: bool = False,
) -> None:
    repo = (repo or "").strip()
    if not repo:
        raise GhManagementError("missing GitHub repo")
    dest_dir = _expand_dir(dest_dir)
    parent = os.path.dirname(dest_dir)
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(dest_dir):
        if is_git_repo(dest_dir):
            return
        if os.path.isfile(dest_dir):
            raise GhManagementError(f"destination exists but is a file: {dest_dir}")
        if _is_empty_dir(dest_dir):
            try:
                os.rmdir(dest_dir)
            except OSError:
                pass
        elif recreate_if_needed and os.path.isdir(dest_dir):
            backup_dir = f"{dest_dir}.bak-{time.time_ns()}"
            try:
                os.replace(dest_dir, backup_dir)
            except OSError as exc:
                raise GhManagementError(
                    f"destination exists but is not a git repo: {dest_dir}\n"
                    f"failed to move it aside to {backup_dir}: {exc}"
                ) from exc
        else:
            raise GhManagementError(
                f"destination exists but is not a git repo: {dest_dir}\n"
                "delete it (or pick a different workspace) and try again"
            )

    proc: subprocess.CompletedProcess[str]
    if prefer_gh and is_gh_available():
        proc = _run(["gh", "repo", "clone", repo, dest_dir], timeout_s=300.0)
    else:
        proc = subprocess.CompletedProcess(args=["gh"], returncode=127, stdout="", stderr="gh not found")
    if proc.returncode != 0:
        proc = _run(["git", "clone", repo, dest_dir], timeout_s=300.0)
    _require_ok(proc, args=["clone", repo, dest_dir])


def prepare_branch_for_task(
    repo_root: str,
    *,
    branch: str,
    base_branch: str | None = None,
) -> tuple[str, str]:
    repo_root = _expand_dir(repo_root)
    if not git_is_clean(repo_root):
        raise GhManagementError("repo has uncommitted changes; commit/stash before running")

    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or git_current_branch(repo_root) or git_default_base_branch(repo_root) or "main"
    _require_ok(_run(["git", "-C", repo_root, "fetch", "--prune"], timeout_s=120.0), args=["git", "fetch"])
    checkout_proc = _run(["git", "-C", repo_root, "checkout", base_branch], timeout_s=20.0)
    if checkout_proc.returncode != 0:
        _require_ok(
            _run(
                ["git", "-C", repo_root, "checkout", "-B", base_branch, f"origin/{base_branch}"],
                timeout_s=20.0,
            ),
            args=["git", "checkout", "-B", base_branch],
        )
    _require_ok(_run(["git", "-C", repo_root, "pull", "--ff-only"], timeout_s=120.0), args=["git", "pull"])

    _require_ok(
        _run(["git", "-C", repo_root, "checkout", "-B", branch], timeout_s=20.0),
        args=["git", "checkout", "-B"],
    )
    return base_branch, branch


def _sanitize_branch(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[^a-zA-Z0-9/_-]+", "-", value)
    value = value.strip("-")
    value = re.sub(r"/{2,}", "/", value)
    return value or "midoriaiagents/task"


def plan_repo_task(
    workdir: str,
    *,
    task_id: str,
    base_branch: str | None = None,
) -> RepoPlan | None:
    workdir = _expand_dir(workdir)
    repo_root = git_repo_root(workdir)
    if repo_root is None:
        return None
    branch = _sanitize_branch(f"midoriaiagents/{task_id}")
    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or git_current_branch(repo_root) or git_default_base_branch(repo_root) or "main"
    return RepoPlan(workdir=workdir, repo_root=repo_root, base_branch=base_branch, branch=branch)


def commit_push_and_pr(
    repo_root: str,
    *,
    branch: str,
    base_branch: str,
    title: str,
    body: str,
    use_gh: bool = True,
) -> str | None:
    repo_root = _expand_dir(repo_root)

    _require_ok(
        _run(["git", "-C", repo_root, "checkout", branch], timeout_s=20.0),
        args=["git", "checkout"],
    )

    proc = _run(["git", "-C", repo_root, "status", "--porcelain"], timeout_s=15.0)
    _require_ok(proc, args=["git", "status"])
    has_worktree_changes = bool((proc.stdout or "").strip())

    if has_worktree_changes:
        _require_ok(_run(["git", "-C", repo_root, "add", "-A"], timeout_s=30.0), args=["git", "add"])
        commit_proc = _run(["git", "-C", repo_root, "commit", "-m", title], timeout_s=60.0)
        if commit_proc.returncode != 0:
            combined = (commit_proc.stdout or "") + "\n" + (commit_proc.stderr or "")
            if "nothing to commit" not in combined.lower():
                _require_ok(commit_proc, args=["git", "commit"])

    ahead_count = None
    for base_ref in (base_branch, f"origin/{base_branch}"):
        count_proc = _run(["git", "-C", repo_root, "rev-list", "--count", f"{base_ref}..HEAD"], timeout_s=15.0)
        if count_proc.returncode == 0:
            try:
                ahead_count = int((count_proc.stdout or "").strip() or "0")
            except ValueError:
                ahead_count = None
            break

    if not has_worktree_changes and (ahead_count is not None and ahead_count <= 0):
        return None

    push_proc = _run(["git", "-C", repo_root, "push", "-u", "origin", branch], timeout_s=180.0)
    _require_ok(push_proc, args=["git", "push"])

    if not use_gh or not is_gh_available():
        return ""

    auth_proc = _run(["gh", "auth", "status"], timeout_s=10.0)
    if auth_proc.returncode != 0:
        raise GhManagementError("`gh` is not authenticated; run `gh auth login`")

    pr_proc = _run(
        [
            "gh",
            "pr",
            "create",
            "--head",
            branch,
            "--base",
            base_branch,
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=repo_root,
        timeout_s=180.0,
    )
    if pr_proc.returncode != 0:
        out = ((pr_proc.stdout or "") + "\n" + (pr_proc.stderr or "")).strip()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("http"):
                return line
        _require_ok(pr_proc, args=["gh", "pr", "create"])
    out = (pr_proc.stdout or "").strip()
    if out.startswith("http"):
        return out.splitlines()[0].strip()
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("http"):
            return line
    return None


def git_list_branches(repo_root: str) -> list[str]:
    repo_root = _expand_dir(repo_root)
    proc = _run(
        ["git", "-C", repo_root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes"],
        timeout_s=10.0,
    )
    if proc.returncode != 0:
        return []
    branches: list[str] = []
    seen: set[str] = set()
    for raw in (proc.stdout or "").splitlines():
        name = (raw or "").strip()
        if not name or name.endswith("/HEAD") or name == "HEAD":
            continue
        if name.startswith("origin/"):
            name = name.removeprefix("origin/").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        branches.append(name)
    return sorted(branches, key=str.casefold)


def git_list_remote_heads(repo: str) -> list[str]:
    repo = (repo or "").strip()
    if not repo:
        return []
    url = repo
    if "://" not in url and not url.startswith("git@") and "/" in url and " " not in url:
        url = f"https://github.com/{url}.git"
    proc = _run(["git", "ls-remote", "--heads", url], timeout_s=20.0)
    if proc.returncode != 0:
        return []
    branches: list[str] = []
    seen: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        parts = (line or "").strip().split()
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/heads/"):
            continue
        name = ref.removeprefix("refs/heads/").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        branches.append(name)
    return sorted(branches, key=str.casefold)
