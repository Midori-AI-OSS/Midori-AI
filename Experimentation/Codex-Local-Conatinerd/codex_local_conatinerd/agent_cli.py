import os
import shlex

from pathlib import Path


SUPPORTED_AGENTS = ("codex", "claude", "copilot")
CONTAINER_HOME = "/home/midori-ai"
CONTAINER_WORKDIR = "/home/midori-ai/workspace"


def normalize_agent(value: str | None) -> str:
    agent = str(value or "").strip().lower()
    return agent if agent in SUPPORTED_AGENTS else "codex"


def container_config_dir(agent: str) -> str:
    agent = normalize_agent(agent)
    if agent == "claude":
        return f"{CONTAINER_HOME}/.claude"
    if agent == "copilot":
        return f"{CONTAINER_HOME}/.copilot"
    return f"{CONTAINER_HOME}/.codex"


def additional_config_mounts(agent: str, host_config_dir: str) -> list[str]:
    agent = normalize_agent(agent)
    host = str(host_config_dir or "").strip()
    if not host:
        return []
    if agent != "claude":
        return []

    # Claude Code stores user-level settings in ~/.claude.json alongside the
    # ~/.claude directory. If the user provided ~/.claude as the config folder,
    # mount the sibling file into the container when present.
    host_dir = Path(os.path.expanduser(host))
    settings_path = host_dir.parent / ".claude.json"
    if settings_path.is_file():
        return [f"{str(settings_path)}:{CONTAINER_HOME}/.claude.json"]
    return []


def verify_cli_clause(agent: str) -> str:
    agent = normalize_agent(agent)
    quoted = shlex.quote(agent)
    return (
        f"command -v {quoted} >/dev/null 2>&1 || "
        "{ "
        f'echo "{agent} not found in PATH=$PATH"; '
        "exit 127; "
        "}; "
    )


def build_noninteractive_cmd(
    *,
    agent: str,
    prompt: str,
    host_workdir: str,
    container_workdir: str = CONTAINER_WORKDIR,
    agent_cli_args: list[str] | None = None,
) -> list[str]:
    agent = normalize_agent(agent)
    extra_args = list(agent_cli_args or [])
    prompt = str(prompt or "").strip()

    if agent == "claude":
        args = [
            "claude",
            "--print",
            "--output-format",
            "text",
            "--permission-mode",
            "bypassPermissions",
            "--add-dir",
            container_workdir,
            *extra_args,
            prompt,
        ]
        return args

    if agent == "copilot":
        args = [
            "copilot",
            "--allow-all-tools",
            "--add-dir",
            container_workdir,
            *extra_args,
            "-p",
            prompt,
        ]
        return args

    # codex
    args = [
        "codex",
        "exec",
        "--sandbox",
        "danger-full-access",
    ]
    if not _is_git_repo_root(host_workdir):
        args.append("--skip-git-repo-check")
    args.extend(extra_args)
    args.append(prompt)
    return args


def _is_git_repo_root(path: str) -> bool:
    return os.path.exists(os.path.join(path, ".git"))

