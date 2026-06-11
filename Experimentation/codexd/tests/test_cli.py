from __future__ import annotations

from pathlib import Path

import pytest

from codexd import cli
from codexd.paths import CodexdPaths


@pytest.fixture()
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CodexdPaths:
    paths = CodexdPaths(
        project_root=tmp_path / "project",
        state_root=tmp_path / "state",
        registry_path=tmp_path / "state" / "registry.toml",
        accounts_root=tmp_path / "state" / "accounts",
        trash_root=tmp_path / "state" / "trash",
        tmp_root=tmp_path / "state" / "tmp",
        compat_home=tmp_path / "compat-home",
        codex_bin=Path("/usr/bin/codex"),
    )
    monkeypatch.setattr(cli.CodexdPaths, "discover", classmethod(lambda cls: paths))
    return paths


def test_root_help_lists_codex_cli_and_codexd_commands(
    isolated_paths: CodexdPaths,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Codex CLI:" in output
    assert "--account NAME" in output
    assert "import NAME" in output
    assert "add NAME" in output
    assert "remove NAME" in output
    assert "manage default NAME" in output
    assert "debug-wrapper" in output
    assert "codex --help" in output


def test_manage_help_describes_summary_and_subcommands(
    isolated_paths: CodexdPaths,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["manage", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "prints the current summary view" in output
    assert "{default,refresh,inspect}" in output
    assert "set the default compatibility account" in output
    assert "refresh cached account status" in output
    assert "print detailed stored metadata for one account" in output


def test_nested_help_pages_include_behavior_descriptions(
    isolated_paths: CodexdPaths,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main(["manage", "refresh", "--help"])
    refresh_output = capsys.readouterr().out
    assert "Refresh stored rate-limit and account status information." in refresh_output
    assert "managed account name to refresh" in refresh_output
    assert "refresh every managed account" in refresh_output

    with pytest.raises(SystemExit):
        cli.main(["import", "--help"])
    import_output = capsys.readouterr().out
    assert "Import the current real ~/.codex home into managed storage." in import_output
    assert "managed account name to create from the current ~/.codex home" in import_output

    with pytest.raises(SystemExit):
        cli.main(["debug-wrapper", "--help"])
    debug_output = capsys.readouterr().out
    assert "maintenance/debug command" in debug_output


def test_debug_wrapper_prints_wrapper_script(
    isolated_paths: CodexdPaths,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["debug-wrapper"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert 'exec uv run --project "' in output
    assert ' codexd "$@"' in output


def test_old_install_wrapper_name_is_no_longer_special(
    isolated_paths: CodexdPaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_launch(self, codex_args: list[str], forced_account: str | None = None) -> None:
        recorded["codex_args"] = codex_args
        recorded["forced_account"] = forced_account

    monkeypatch.setattr(cli.CodexdService, "launch", fake_launch)

    exit_code = cli.main(["install-wrapper-preview"])

    assert exit_code == 0
    assert recorded["codex_args"] == ["install-wrapper-preview"]
    assert recorded["forced_account"] is None
