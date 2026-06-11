from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path


STATE_ROOT_ENV = "CODEXD_STATE_ROOT"
COMPAT_HOME_ENV = "CODEXD_COMPAT_HOME"
CODEX_BIN_ENV = "CODEXD_CODEX_BIN"


@dataclass(slots=True)
class CodexdPaths:
    project_root: Path
    state_root: Path
    registry_path: Path
    accounts_root: Path
    trash_root: Path
    tmp_root: Path
    compat_home: Path
    codex_bin: Path

    @classmethod
    def discover(cls) -> "CodexdPaths":
        project_root = Path(__file__).resolve().parents[2]
        state_root = _expand_path(
            os.environ.get(STATE_ROOT_ENV, "~/.midoriai/.codexd"),
        )
        compat_home = _expand_path(
            os.environ.get(COMPAT_HOME_ENV, "~/.codex"),
        )
        codex_bin = _expand_path(
            os.environ.get(CODEX_BIN_ENV, "/usr/bin/codex"),
        )
        return cls(
            project_root=project_root,
            state_root=state_root,
            registry_path=state_root / "registry.toml",
            accounts_root=state_root / "accounts",
            trash_root=state_root / "trash",
            tmp_root=state_root / "tmp",
            compat_home=compat_home,
            codex_bin=codex_bin,
        )


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()
