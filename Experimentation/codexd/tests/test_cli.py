from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from codexd import cli
from codexd.models import AccountRecord
from codexd.models import AccountStatusSnapshot
from codexd.models import RateLimitWindow
from codexd.models import Registry
from codexd.models import StatusReadResult
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
        cli.main(["add", "--help"])
    add_output = capsys.readouterr().out
    assert "Provide the access token on stdin or through CODEX_ACCESS_TOKEN." in add_output
    assert "--allow-file-auth" in add_output

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


def test_manage_summary_shows_remaining_quota_with_duration_labels(
    isolated_paths: CodexdPaths,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = Registry(
        default_account="Riley-Midori",
        accounts={
            "Riley-Midori": AccountRecord(
                name="Riley-Midori",
                home_path="/tmp/riley",
                created_at="2026-06-10T00:00:00Z",
                last_status_source="live",
                last_primary_used_percent=40,
                last_primary_window_duration_mins=300,
                last_secondary_used_percent=75,
                last_secondary_window_duration_mins=10080,
                last_plan_type="plus",
            ),
        },
    )

    monkeypatch.setattr(
        cli.CodexdService,
        "manage_summary",
        lambda self: (registry, SimpleNamespace(name="Riley-Midori")),
    )

    exit_code = cli.main(["manage"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "default_account = Riley-Midori" in output
    assert "auto_pick_now = Riley-Midori" in output
    assert "Riley-Midori [default]: Plan: Plus | 5-hours: 60% | Weekly: 25%" in output


def test_manage_refresh_shows_remaining_quota_with_live_snapshot(
    isolated_paths: CodexdPaths,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli.CodexdService,
        "refresh_status",
        lambda self, target: {
            "Riley-Midori": StatusReadResult(
                source="live",
                snapshot=AccountStatusSnapshot(
                    plan_type="plus",
                    primary=RateLimitWindow(used_percent=40, window_duration_mins=300),
                    secondary=RateLimitWindow(
                        used_percent=75,
                        window_duration_mins=10080,
                    ),
                ),
            ),
        },
    )

    exit_code = cli.main(["manage", "refresh", "--all"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Riley-Midori: Plan: Plus | 5-hours: 60% | Weekly: 25%" in output


def test_manage_summary_falls_back_to_generic_window_labels_when_duration_missing(
    isolated_paths: CodexdPaths,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = Registry(
        default_account=None,
        accounts={
            "main": AccountRecord(
                name="main",
                home_path="/tmp/main",
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=1,
                last_secondary_used_percent=0,
                last_plan_type="team",
            ),
        },
    )

    monkeypatch.setattr(
        cli.CodexdService,
        "manage_summary",
        lambda self: (registry, SimpleNamespace(name="main")),
    )

    exit_code = cli.main(["manage"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "main: Plan: Team | Primary: 99% | Secondary: 100%" in output
