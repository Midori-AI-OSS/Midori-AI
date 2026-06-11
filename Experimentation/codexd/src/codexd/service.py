from __future__ import annotations

import os
import shutil
import subprocess
import sys

from pathlib import Path
from datetime import UTC
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from codexd import ranking
from codexd.app_server import read_live_status
from codexd.app_server import StatusReadFailure
from codexd.importer import copy_codex_home
from codexd.importer import verify_import
from codexd.importer import should_exclude
from codexd.importer import ensure_compat_symlink
from codexd.importer import detect_active_reasons
from codexd.importer import remove_compat_symlink
from codexd.launcher import exec_codex
from codexd.models import Registry
from codexd.models import StatusReadResult
from codexd.models import AccountRecord
from codexd.paths import CodexdPaths
from codexd.registry import load_registry
from codexd.registry import save_registry
from codexd.registry import ensure_state_layout
from codexd.session_snapshot import read_session_snapshot


class CodexdError(RuntimeError):
    pass


class CodexdService:
    def __init__(self, paths: CodexdPaths) -> None:
        self.paths = paths
        ensure_state_layout(paths)

    def manage_summary(self) -> tuple[Registry, ranking.SelectionDecision | None]:
        registry = self._load_registry()
        if not registry.accounts:
            return registry, None
        decision = ranking.choose_account(registry)
        return registry, decision

    def inspect_account(self, name: str) -> AccountRecord:
        registry = self._load_registry()
        record = registry.accounts.get(name)
        if record is None:
            raise CodexdError(f"Unknown account: {name}")
        return record

    def import_current_home(self, name: str, prompt=input) -> AccountRecord:
        registry = self._load_registry()
        if name in registry.accounts:
            raise CodexdError(f"Account already exists: {name}")
        source_home = self.paths.compat_home
        if source_home.is_symlink():
            raise CodexdError(
                f"{source_home} is already a symlink. Import expects the current real ~/.codex home.",
            )
        if not source_home.exists():
            raise CodexdError(f"Nothing to import from {source_home}")

        reasons = detect_active_reasons(source_home)
        if reasons:
            if not _confirm_force_import(prompt):
                raise CodexdError(
                    "Import aborted because ~/.codex appears active. Close Codex and retry, or confirm the force prompt.",
                )

        account_home = self._account_home(name)
        account_home.parent.mkdir(parents=True, exist_ok=True)
        snapshot = self._prepare_import_home(name, source_home, account_home)
        moved_source = source_home
        shutil.rmtree(moved_source)
        ensure_compat_symlink(self.paths.compat_home, account_home)

        record = AccountRecord(
            name=name,
            home_path=str(account_home),
            created_at=_now_iso(),
            imported_from_current_codex_home=True,
        )
        record.apply_status(StatusReadResult(source="live", snapshot=snapshot), _now_iso())
        registry.accounts[name] = record
        registry.default_account = name
        self._save_registry(registry)
        return record

    def _prepare_import_home(
        self,
        name: str,
        source_home: Path,
        account_home: Path,
    ) -> AccountStatusSnapshot:
        if account_home.exists():
            try:
                return verify_import(source_home, account_home, self._read_status_snapshot)
            except (RuntimeError, StatusReadFailure) as exc:
                archive_dir = self._archive_partial_import_home(name, account_home)
                print(
                    f"warning: archived failed partial import at {archive_dir} before retrying import",
                    file=sys.stderr,
                )
                copy_error = exc
            else:
                copy_error = None
        else:
            copy_error = None

        try:
            copy_codex_home(source_home, account_home)
            return verify_import(source_home, account_home, self._read_status_snapshot)
        except (RuntimeError, StatusReadFailure) as exc:
            detail = str(exc)
            if copy_error is not None:
                detail = f"{detail} (previous partial import error: {copy_error})"
            raise CodexdError(
                f"Import verification failed for managed home {account_home}: {detail}",
            ) from exc

    def _archive_partial_import_home(self, name: str, account_home: Path) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = self.paths.trash_root / f"{timestamp}-{name}-partial-import"
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(account_home), archive_dir)
        return archive_dir

    def add_account(self, name: str) -> AccountRecord:
        registry = self._load_registry()
        if name in registry.accounts:
            raise CodexdError(f"Account already exists: {name}")
        account_home = self._account_home(name)
        account_home.mkdir(parents=True, exist_ok=False)
        _run_interactive(
            [str(self.paths.codex_bin), "login"],
            self._account_env(account_home),
        )
        login_status = subprocess.run(
            [str(self.paths.codex_bin), "login", "status"],
            capture_output=True,
            check=False,
            env=self._account_env(account_home),
            text=True,
        )
        if login_status.returncode != 0:
            raise CodexdError(
                f"codex login status failed for {name}: {login_status.stderr.strip() or login_status.stdout.strip()}",
            )
        record = AccountRecord(
            name=name,
            home_path=str(account_home),
            created_at=_now_iso(),
            imported_from_current_codex_home=False,
        )
        registry.accounts[name] = record
        self._save_registry(registry)
        self.refresh_status(name)

        registry = self._load_registry()
        if registry.default_account is None and (
            not self.paths.compat_home.exists() or self.paths.compat_home.is_symlink()
        ):
            registry.default_account = name
            self._save_registry(registry)
            ensure_compat_symlink(self.paths.compat_home, account_home)
        return registry.accounts[name]

    def remove_account(self, name: str) -> str | None:
        registry = self._load_registry()
        record = registry.accounts.get(name)
        if record is None:
            raise CodexdError(f"Unknown account: {name}")

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = self.paths.trash_root / f"{timestamp}-{name}"
        archive_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(record.home_path, archive_dir)
        was_default = registry.default_account == name
        del registry.accounts[name]
        if not registry.accounts:
            registry.default_account = None
            self._save_registry(registry)
            remove_compat_symlink(self.paths.compat_home)
            return None

        if was_default:
            registry.default_account = None
            self._save_registry(registry)
            live_results = self.refresh_status("--all", persist=False)
            registry = self._load_registry()
            decision = ranking.choose_account(registry, live_results)
            registry.default_account = decision.name
            self._save_registry(registry)
            ensure_compat_symlink(self.paths.compat_home, self._account_home(decision.name))
            return decision.name

        self._save_registry(registry)
        return registry.default_account

    def set_default_account(self, name: str) -> AccountRecord:
        registry = self._load_registry()
        record = registry.accounts.get(name)
        if record is None:
            raise CodexdError(f"Unknown account: {name}")
        ensure_compat_symlink(self.paths.compat_home, Path(record.home_path))
        registry.default_account = name
        self._save_registry(registry)
        return record

    def refresh_status(
        self,
        target: str,
        persist: bool = True,
    ) -> dict[str, StatusReadResult]:
        registry = self._load_registry()
        if not registry.accounts:
            raise CodexdError("No managed accounts are registered")
        if target == "--all":
            names = sorted(registry.accounts)
        else:
            if target not in registry.accounts:
                raise CodexdError(f"Unknown account: {target}")
            names = [target]

        results: dict[str, StatusReadResult] = {}
        with ThreadPoolExecutor(max_workers=len(names)) as executor:
            futures = {
                executor.submit(self._read_status_result, Path(registry.accounts[name].home_path)): name
                for name in names
            }
            for future, name in futures.items():
                result = future.result()
                results[name] = result

        if persist:
            now = _now_iso()
            for name, result in results.items():
                registry.accounts[name].apply_status(result, now)
            self._save_registry(registry)
        return results

    def launch(self, codex_args: list[str], forced_account: str | None = None) -> None:
        registry = self._load_registry()
        if not registry.accounts:
            raise CodexdError("No managed accounts are registered")
        if forced_account is not None:
            record = registry.accounts.get(forced_account)
            if record is None:
                raise CodexdError(f"Unknown account: {forced_account}")
            selected_name = forced_account
        else:
            live_results = self.refresh_status("--all", persist=True)
            registry = self._load_registry()
            decision = ranking.choose_account(registry, live_results)
            if decision.warning is not None:
                print(f"warning: {decision.warning}", file=sys.stderr)
            selected_name = decision.name

        registry = self._load_registry()
        record = registry.accounts[selected_name]
        timestamp = _now_iso()
        record.last_selected_at = timestamp
        record.last_successful_launch_at = timestamp
        self._save_registry(registry)
        exec_codex(self.paths.codex_bin, Path(record.home_path), codex_args)

    def _load_registry(self) -> Registry:
        return load_registry(self.paths.registry_path)

    def _save_registry(self, registry: Registry) -> None:
        save_registry(self.paths.registry_path, registry)

    def _account_home(self, name: str) -> Path:
        return self.paths.accounts_root / name / "home"

    def _account_env(self, home_path: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["CODEX_HOME"] = str(home_path)
        return env

    def _read_status_snapshot(self, home_path: Path):
        return read_live_status(home_path, self.paths.codex_bin)

    def _read_status_result(self, home_path: Path) -> StatusReadResult:
        try:
            return StatusReadResult(
                source="live",
                snapshot=self._read_status_snapshot(home_path),
            )
        except StatusReadFailure as exc:
            snapshot = read_session_snapshot(home_path)
            if snapshot is not None:
                return StatusReadResult(
                    source="session_snapshot",
                    snapshot=snapshot,
                    error=str(exc),
                )
            return StatusReadResult(
                source="error",
                snapshot=None,
                error=str(exc),
            )


def _confirm_force_import(prompt) -> bool:
    answer = prompt("~/.codex appears to be active. Force import anyway? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_interactive(command: list[str], env: dict[str, str]) -> None:
    returncode = subprocess.call(command, env=env)
    if returncode != 0:
        raise CodexdError(f"Command failed with exit code {returncode}: {' '.join(command)}")
