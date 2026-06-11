from __future__ import annotations

import tomllib

from pathlib import Path

import tomli_w

from codexd.models import Registry
from codexd.models import AccountRecord
from codexd.paths import CodexdPaths


def ensure_state_layout(paths: CodexdPaths) -> None:
    paths.state_root.mkdir(parents=True, exist_ok=True)
    paths.accounts_root.mkdir(parents=True, exist_ok=True)
    paths.trash_root.mkdir(parents=True, exist_ok=True)
    paths.tmp_root.mkdir(parents=True, exist_ok=True)


def load_registry(path: Path) -> Registry:
    if not path.exists():
        return Registry()
    payload = tomllib.loads(path.read_text())
    default_account = payload.get("default_account")
    accounts_payload = payload.get("accounts", {})
    accounts: dict[str, AccountRecord] = {}
    if isinstance(accounts_payload, dict):
        for name, record_payload in accounts_payload.items():
            if isinstance(name, str) and isinstance(record_payload, dict):
                accounts[name] = AccountRecord.from_registry_dict(name, record_payload)
    return Registry(
        default_account=default_account if isinstance(default_account, str) else None,
        accounts=accounts,
    )


def save_registry(path: Path, registry: Registry) -> None:
    payload = _strip_none(
        {
        "default_account": registry.default_account,
        "accounts": {
            name: record.to_registry_dict()
            for name, record in sorted(registry.accounts.items())
        },
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        tomli_w.dump(payload, handle)


def _strip_none(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _strip_none(child)
            for key, child in value.items()
            if child is not None
        }
    if isinstance(value, list):
        return [_strip_none(child) for child in value]
    return value
