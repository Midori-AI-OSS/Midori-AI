from __future__ import annotations

from pathlib import Path

from codexd.models import Registry
from codexd.models import AccountRecord
from codexd.registry import load_registry
from codexd.registry import save_registry


def test_registry_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "registry.toml"
    registry = Registry(
        default_account="team",
        accounts={
            "team": AccountRecord(
                name="team",
                home_path="/tmp/team",
                created_at="2026-06-10T00:00:00Z",
                imported_from_current_codex_home=True,
                last_status_source="live",
                last_primary_used_percent=12,
                last_secondary_used_percent=34,
                last_plan_type="team",
            ),
        },
    )

    save_registry(path, registry)
    loaded = load_registry(path)

    assert loaded.default_account == "team"
    assert loaded.accounts["team"].home_path == "/tmp/team"
    assert loaded.accounts["team"].last_primary_used_percent == 12
    assert loaded.accounts["team"].last_plan_type == "team"
