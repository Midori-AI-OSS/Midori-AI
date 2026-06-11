from __future__ import annotations

import tomllib

from pathlib import Path

import pytest

from codexd.models import StatusReadResult
from codexd.models import RateLimitWindow
from codexd.models import AccountStatusSnapshot
from codexd.paths import CodexdPaths
from codexd.app_server import StatusReadFailure
from codexd.registry import load_registry
from codexd.registry import save_registry
from codexd.service import CodexdService
from codexd.models import Registry
from codexd.models import AccountRecord


def test_manage_refresh_uses_cached_snapshot_when_live_read_fails(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    registry = Registry(
        default_account="main",
        accounts={
            "main": AccountRecord(
                name="main",
                home_path=str(paths.accounts_root / "main" / "home"),
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=18,
                last_secondary_used_percent=44,
                last_plan_type="team",
            ),
        },
    )
    (paths.accounts_root / "main" / "home").mkdir(parents=True)
    save_registry(paths.registry_path, registry)

    service._read_status_result = lambda home: StatusReadResult(source="error", error="down")  # type: ignore[method-assign]
    results = service.refresh_status("main")

    loaded = tomllib.loads(paths.registry_path.read_text())
    account = loaded["accounts"]["main"]

    assert results["main"].source == "error"
    assert account["last_primary_used_percent"] == 18
    assert account["last_status_error"] == "down"


def test_default_symlink_updates_and_reassignment(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    first_home = paths.accounts_root / "alpha" / "home"
    second_home = paths.accounts_root / "beta" / "home"
    first_home.mkdir(parents=True)
    second_home.mkdir(parents=True)
    registry = Registry(
        default_account="alpha",
        accounts={
            "alpha": AccountRecord(
                name="alpha",
                home_path=str(first_home),
                created_at="2026-06-10T00:00:00Z",
            ),
            "beta": AccountRecord(
                name="beta",
                home_path=str(second_home),
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=10,
            ),
        },
    )
    save_registry(paths.registry_path, registry)
    paths.compat_home.symlink_to(first_home)
    service._read_status_result = lambda home: StatusReadResult(  # type: ignore[method-assign]
        source="live",
        snapshot=AccountStatusSnapshot(
            primary=RateLimitWindow(used_percent=10 if home == second_home else 90),
        ),
    )

    replacement = service.remove_account("alpha")

    assert replacement == "beta"
    assert paths.compat_home.resolve() == second_home.resolve()


def test_import_verification_keeps_durable_files_and_replaces_compat_home(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    compat_home = paths.compat_home
    compat_home.mkdir(parents=True)
    (compat_home / "auth.json").write_text("{}")
    (compat_home / "config.toml").write_text("model = 'gpt-5'\n")
    (compat_home / "history.jsonl").write_text("{}\n")
    (compat_home / "sessions").mkdir()
    (compat_home / "state_5.sqlite").write_text("db")
    (compat_home / "state_5.sqlite-wal").write_text("skip")

    service._read_status_snapshot = lambda home: AccountStatusSnapshot(  # type: ignore[method-assign]
        plan_type="team",
        primary=RateLimitWindow(used_percent=1),
    )

    record = service.import_current_home("team", prompt=lambda _: "y")
    imported_home = Path(record.home_path)

    assert compat_home.is_symlink()
    assert compat_home.resolve() == imported_home.resolve()
    assert (imported_home / "auth.json").exists()
    assert (imported_home / "config.toml").exists()
    assert not (imported_home / "state_5.sqlite-wal").exists()


def test_import_resumes_existing_valid_partial_home(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    compat_home = paths.compat_home
    compat_home.mkdir(parents=True)
    _seed_codex_home(compat_home)
    existing_home = paths.accounts_root / "team" / "home"
    existing_home.mkdir(parents=True)
    _seed_codex_home(existing_home)

    service._read_status_snapshot = lambda home: AccountStatusSnapshot(  # type: ignore[method-assign]
        plan_type="team",
        primary=RateLimitWindow(used_percent=5),
    )

    record = service.import_current_home("team", prompt=lambda _: "y")

    registry = load_registry(paths.registry_path)
    assert record.home_path == str(existing_home)
    assert registry.default_account == "team"
    assert paths.compat_home.is_symlink()
    assert paths.compat_home.resolve() == existing_home.resolve()


def test_import_archives_invalid_partial_home_then_retries(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    compat_home = paths.compat_home
    compat_home.mkdir(parents=True)
    _seed_codex_home(compat_home)
    invalid_home = paths.accounts_root / "team" / "home"
    invalid_home.mkdir(parents=True)
    (invalid_home / "config.toml").write_text("model = 'wrong'\n")

    service._read_status_snapshot = lambda home: AccountStatusSnapshot(  # type: ignore[method-assign]
        plan_type="team",
        primary=RateLimitWindow(used_percent=5),
    )

    record = service.import_current_home("team", prompt=lambda _: "y")

    trash_entries = sorted(paths.trash_root.glob("*-team-partial-import"))
    assert trash_entries
    assert (trash_entries[0] / "config.toml").read_text() == "model = 'wrong'\n"
    assert Path(record.home_path).exists()
    assert paths.compat_home.is_symlink()


def test_import_failure_raises_codexd_error_instead_of_raw_traceback(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = CodexdService(paths)
    compat_home = paths.compat_home
    compat_home.mkdir(parents=True)
    _seed_codex_home(compat_home)

    def fail_status(home: Path) -> AccountStatusSnapshot:
        raise StatusReadFailure("missing account data")

    service._read_status_snapshot = fail_status  # type: ignore[method-assign]

    with pytest.raises(Exception) as exc_info:
        service.import_current_home("team", prompt=lambda _: "y")

    assert "Import verification failed for managed home" in str(exc_info.value)


def _paths(tmp_path: Path) -> CodexdPaths:
    state_root = tmp_path / "state"
    compat_home = tmp_path / "compat-home"
    return CodexdPaths(
        project_root=tmp_path / "project",
        state_root=state_root,
        registry_path=state_root / "registry.toml",
        accounts_root=state_root / "accounts",
        trash_root=state_root / "trash",
        tmp_root=state_root / "tmp",
        compat_home=compat_home,
        codex_bin=Path("/usr/bin/codex"),
    )


def _seed_codex_home(home: Path) -> None:
    (home / "auth.json").write_text("{}")
    (home / "config.toml").write_text("model = 'gpt-5'\n")
    (home / "history.jsonl").write_text("{}\n")
    (home / "sessions").mkdir(exist_ok=True)
    (home / "state_5.sqlite").write_text("db")
