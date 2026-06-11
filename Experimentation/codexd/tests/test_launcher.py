from __future__ import annotations

from pathlib import Path

from codexd.launcher import build_codex_command
from codexd.launcher import is_admin_passthrough_command


def test_build_codex_command_injects_sandbox_for_plain_launch() -> None:
    command = build_codex_command(Path("/usr/bin/codex"), [])

    assert command == ["/usr/bin/codex", "--sandbox", "danger-full-access"]


def test_build_codex_command_does_not_inject_sandbox_for_login() -> None:
    command = build_codex_command(Path("/usr/bin/codex"), ["login"])

    assert command == ["/usr/bin/codex", "login"]


def test_build_codex_command_does_not_inject_sandbox_for_login_after_global_flags() -> None:
    command = build_codex_command(
        Path("/usr/bin/codex"),
        ["--model", "gpt-5.5", "login"],
    )

    assert command == ["/usr/bin/codex", "--model", "gpt-5.5", "login"]


def test_admin_passthrough_detects_logout() -> None:
    assert is_admin_passthrough_command(["logout"]) is True


def test_admin_passthrough_does_not_treat_prompt_as_subcommand() -> None:
    assert is_admin_passthrough_command(["fix", "the", "tests"]) is False
