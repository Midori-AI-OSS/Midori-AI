from __future__ import annotations

import os

from pathlib import Path


KNOWN_SUBCOMMANDS = {
    "exec",
    "review",
    "login",
    "logout",
    "mcp",
    "plugin",
    "mcp-server",
    "app-server",
    "remote-control",
    "completion",
    "update",
    "doctor",
    "sandbox",
    "debug",
    "apply",
    "resume",
    "fork",
    "cloud",
    "exec-server",
    "features",
    "help",
}
SANDBOX_RUN_SUBCOMMANDS = {"exec", "review", "resume", "fork", "cloud"}
ADMIN_PASSTHROUGH_SUBCOMMANDS = KNOWN_SUBCOMMANDS - SANDBOX_RUN_SUBCOMMANDS
FLAGS_WITH_VALUE = {
    "-c",
    "--config",
    "--enable",
    "--disable",
    "--remote",
    "--remote-auth-token-env",
    "-i",
    "--image",
    "-m",
    "--model",
    "--local-provider",
    "-p",
    "--profile",
    "-s",
    "--sandbox",
    "-C",
    "--cd",
    "--add-dir",
    "-a",
    "--ask-for-approval",
}


def build_codex_command(codex_bin: Path, codex_args: list[str]) -> list[str]:
    command = [str(codex_bin)]
    command.extend(codex_args)
    if _should_inject_sandbox(codex_args) and not _has_explicit_sandbox(codex_args):
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


def is_admin_passthrough_command(codex_args: list[str]) -> bool:
    subcommand = _extract_subcommand(codex_args)
    return subcommand in ADMIN_PASSTHROUGH_SUBCOMMANDS


def _should_inject_sandbox(codex_args: list[str]) -> bool:
    subcommand = _extract_subcommand(codex_args)
    if subcommand is None:
        return True
    return subcommand in SANDBOX_RUN_SUBCOMMANDS


def _extract_subcommand(codex_args: list[str]) -> str | None:
    index = 0
    while index < len(codex_args):
        arg = codex_args[index]
        if arg in {"-h", "--help", "-V", "--version"}:
            return "help"
        if arg.startswith("-"):
            if arg in FLAGS_WITH_VALUE and index + 1 < len(codex_args):
                index += 2
                continue
            index += 1
            continue
        return arg if arg in KNOWN_SUBCOMMANDS else None
    return None
