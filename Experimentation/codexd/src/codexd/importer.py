from __future__ import annotations

import fnmatch
import shutil
import hashlib

from pathlib import Path

from codexd.models import AccountStatusSnapshot


TRANSIENT_FILE_PATTERNS = (
    "*.sqlite-shm",
    "*.sqlite-wal",
    "*.pid",
    "*.sock",
    "*.socket",
    "*.lock",
)
TRANSIENT_DIR_NAMES = {
    ".tmp",
    "tmp",
    "session-state",
}


def detect_active_reasons(source_home: Path) -> list[str]:
    reasons: list[str] = []
    for pattern in TRANSIENT_FILE_PATTERNS:
        match = next(source_home.rglob(pattern), None)
        if match is not None:
            reasons.append(f"found transient file {match.relative_to(source_home)}")
    for directory_name in sorted(TRANSIENT_DIR_NAMES):
        match = next(
            (path for path in source_home.rglob(directory_name) if path.is_dir()),
            None,
        )
        if match is not None:
            reasons.append(f"found runtime directory {match.relative_to(source_home)}")
    return reasons


def copy_codex_home(source_home: Path, destination_home: Path) -> None:
    if destination_home.exists():
        raise RuntimeError(f"Destination already exists: {destination_home}")
    shutil.copytree(
        source_home,
        destination_home,
        ignore=_copytree_ignore,
        copy_function=shutil.copy2,
        dirs_exist_ok=False,
    )


def verify_import(
    source_home: Path,
    destination_home: Path,
    status_reader,
) -> AccountStatusSnapshot:
    if not destination_home.exists() or not destination_home.is_dir():
        raise RuntimeError("Imported home was not created")
    if not destination_home.stat().st_mode:
        raise RuntimeError("Imported home is not readable")

    source_auth = source_home / "auth.json"
    if source_auth.exists() and not (destination_home / "auth.json").exists():
        raise RuntimeError("Imported home is missing auth.json")

    source_config = source_home / "config.toml"
    if source_config.exists():
        destination_config = destination_home / "config.toml"
        if _sha256(source_config) != _sha256(destination_config):
            raise RuntimeError("config.toml hash mismatch after import")

    for sqlite_path in sorted(source_home.glob("*.sqlite")):
        if not (destination_home / sqlite_path.name).exists():
            raise RuntimeError(f"Imported home is missing {sqlite_path.name}")

    source_sessions = source_home / "sessions"
    if source_sessions.exists() and not (destination_home / "sessions").exists():
        raise RuntimeError("Imported home is missing sessions directory")

    return status_reader(destination_home)


def ensure_compat_symlink(compat_home: Path, target: Path) -> None:
    if compat_home.exists() and not compat_home.is_symlink():
        raise RuntimeError(
            f"{compat_home} is a real path. Import it first before repointing the compatibility link.",
        )
    if compat_home.is_symlink() or compat_home.exists():
        compat_home.unlink()
    compat_home.parent.mkdir(parents=True, exist_ok=True)
    compat_home.symlink_to(target)
    if compat_home.resolve() != target.resolve():
        raise RuntimeError("Failed to verify compatibility symlink target")


def remove_compat_symlink(compat_home: Path) -> None:
    if compat_home.is_symlink():
        compat_home.unlink()


def should_exclude(relative_path: Path, is_dir: bool) -> bool:
    name = relative_path.name
    if is_dir and name in TRANSIENT_DIR_NAMES:
        return True
    if not is_dir and any(fnmatch.fnmatch(name, pattern) for pattern in TRANSIENT_FILE_PATTERNS):
        return True
    if any(part.startswith("arg0-") for part in relative_path.parts):
        return True
    return False


def _copytree_ignore(base: str, names: list[str]) -> set[str]:
    base_path = Path(base)
    ignored: set[str] = set()
    for name in names:
        path = base_path / name
        relative_path = Path(name)
        if should_exclude(relative_path, path.is_dir()):
            ignored.add(name)
    return ignored


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
