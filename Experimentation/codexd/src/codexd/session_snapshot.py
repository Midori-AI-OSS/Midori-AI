from __future__ import annotations

import json

from pathlib import Path

from codexd.models import AccountStatusSnapshot


def read_session_snapshot(codex_home: Path) -> AccountStatusSnapshot | None:
    roots = [
        codex_home / "session-state",
        codex_home / "sessions",
    ]
    newest_snapshot = None
    newest_mtime = -1.0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".jsonl"}:
                continue
            snapshot = _read_snapshot_file(path)
            if snapshot is None:
                continue
            mtime = path.stat().st_mtime
            if mtime >= newest_mtime:
                newest_snapshot = snapshot
                newest_mtime = mtime
    return newest_snapshot


def _read_snapshot_file(path: Path) -> AccountStatusSnapshot | None:
    if path.suffix == ".jsonl":
        latest = None
        for line in path.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidate = _find_snapshot(payload)
            if candidate is not None:
                latest = candidate
        return latest
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return _find_snapshot(payload)


def _find_snapshot(payload: object) -> AccountStatusSnapshot | None:
    if isinstance(payload, dict):
        if "rateLimits" in payload:
            snapshot = AccountStatusSnapshot.from_api(None, payload)
            if snapshot.primary is not None or snapshot.secondary is not None:
                return snapshot
        for value in payload.values():
            snapshot = _find_snapshot(value)
            if snapshot is not None:
                return snapshot
    if isinstance(payload, list):
        for value in payload:
            snapshot = _find_snapshot(value)
            if snapshot is not None:
                return snapshot
    return None
