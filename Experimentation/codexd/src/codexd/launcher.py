from __future__ import annotations

import os

from pathlib import Path


def build_codex_command(codex_bin: Path, codex_args: list[str]) -> list[str]:
    command = [str(codex_bin)]
    command.extend(codex_args)
    if not _has_explicit_sandbox(codex_args):
        command.extend(["--sandbox", "danger-full-access"])
    return command


def exec_codex(codex_bin: Path, codex_home: Path, codex_args: list[str]) -> None:
    command = build_codex_command(codex_bin, codex_args)
    env = dict(os.environ)
    env["CODEX_HOME"] = str(codex_home)
    os.execvpe(command[0], command, env)


def _has_explicit_sandbox(codex_args: list[str]) -> bool:
    for arg in codex_args:
        if arg in {"-s", "--sandbox", "--dangerously-bypass-approvals-and-sandbox"}:
            return True
        if arg.startswith("--sandbox="):
            return True
    return False
