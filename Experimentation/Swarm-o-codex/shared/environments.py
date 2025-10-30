from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import toml


ProjectRoot = Path(__file__).resolve().parents[1]
PROFILE_DIR = ProjectRoot / "profile"
PROFILE_DIR.mkdir(exist_ok=True)
META_PATH = PROFILE_DIR / "environments.toml"
STORE_ROOT = ProjectRoot / ".environments"
STORE_ROOT.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_meta() -> Dict:
    if not META_PATH.exists():
        return {"environments": {}}
    try:
        return toml.load(META_PATH)
    except Exception:
        # if the file is corrupt, return empty structure
        return {"environments": {}}


def _write_meta(data: Dict) -> None:
    tmp = META_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        toml.dump(data, f)
    os.replace(tmp, META_PATH)


def _run_git(args, cwd: Optional[Path] = None):
    cmd = ["git", *args]
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd is not None else None)


@dataclass
class Environment:
    name: str
    repo: str
    path: str
    created_at: str
    last_updated: str
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


def list_environments() -> Dict[str, Environment]:
    data = _load_meta()
    envs = {}
    for k, v in data.get("environments", {}).items():
        envs[k] = Environment(name=k, **v)
    return envs


def get_environment(name: str) -> Optional[Environment]:
    envs = list_environments()
    return envs.get(name)


def add_environment(name: str, repo_url: str, overwrite: bool = False, mirror: bool = True) -> Environment:
    if not name or any(c in name for c in ("/", "\\")):
        raise ValueError("Invalid environment name")

    data = _load_meta()
    envs = data.setdefault("environments", {})
    if name in envs and not overwrite:
        raise ValueError(f"environment '{name}' already exists")

    env_dir = STORE_ROOT / name
    mirror_dir = env_dir / "mirror.git"
    # ensure env_dir exists
    env_dir.mkdir(parents=True, exist_ok=True)

    try:
        if mirror:
            # clone a mirror (all refs)
            if mirror_dir.exists():
                shutil.rmtree(mirror_dir)
            _run_git(["clone", "--mirror", repo_url, str(mirror_dir)])
            path_to_store = str(mirror_dir)
        else:
            # normal full clone
            worktree = env_dir / "repo"
            if worktree.exists():
                shutil.rmtree(worktree)
            _run_git(["clone", repo_url, str(worktree)])
            path_to_store = str(worktree)

        now = _now_iso()
        env_entry = {
            "repo": repo_url,
            "path": path_to_store,
            "created_at": now if name not in envs else envs[name].get("created_at", now),
            "last_updated": now,
        }
        envs[name] = env_entry
        _write_meta(data)
        return Environment(name=name, **env_entry)
    except Exception:
        # cleanup partial clones on failure
        if env_dir.exists():
            shutil.rmtree(env_dir)
        raise


def remove_environment(name: str, delete_files: bool = False) -> bool:
    data = _load_meta()
    envs = data.get("environments", {})
    if name not in envs:
        return False
    env_entry = envs.pop(name)
    _write_meta(data)
    if delete_files:
        p = Path(env_entry.get("path", ""))
        # path may be inside STORE_ROOT/name
        if p.exists():
            # be careful to only delete inside store root
            try:
                p_parent = Path(p).resolve().parent
                if STORE_ROOT.resolve() in p.resolve().parents or STORE_ROOT.resolve() == p.resolve() or STORE_ROOT.resolve() in p_parent.parents:
                    shutil.rmtree(STORE_ROOT / name)
            except Exception:
                pass
    return True


def update_environment(name: str) -> bool:
    env = get_environment(name)
    if not env:
        return False
    p = Path(env.path)
    if not p.exists():
        return False
    try:
        # For mirror repos, use remote update
        if p.name.endswith(".git"):
            _run_git(["remote", "update", "--prune"], cwd=p)
        else:
            _run_git(["fetch", "--all", "--prune"], cwd=p)
        data = _load_meta()
        data.setdefault("environments", {})[name]["last_updated"] = _now_iso()
        _write_meta(data)
        return True
    except Exception:
        return False
