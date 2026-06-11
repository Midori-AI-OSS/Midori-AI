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
                auth_mode="imported_home",
                credential_store_mode="file",
                last_status_source="live",
                last_primary_used_percent=12,
                last_primary_window_duration_mins=300,
                last_secondary_used_percent=34,
                last_secondary_window_duration_mins=10080,
                last_plan_type="team",
            ),
        },
    )

    save_registry(path, registry)
    loaded = load_registry(path)

    assert loaded.default_account == "team"
    assert loaded.accounts["team"].home_path == "/tmp/team"
    assert loaded.accounts["team"].auth_mode == "imported_home"
    assert loaded.accounts["team"].credential_store_mode == "file"
    assert loaded.accounts["team"].last_primary_used_percent == 12
    assert loaded.accounts["team"].last_primary_window_duration_mins == 300
    assert loaded.accounts["team"].last_plan_type == "team"


def test_cached_snapshot_restores_window_durations(tmp_path: Path) -> None:
    path = tmp_path / "registry.toml"
    registry = Registry(
        default_account="plus",
        accounts={
            "plus": AccountRecord(
                name="plus",
                home_path="/tmp/plus",
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=40,
                last_primary_window_duration_mins=300,
                last_secondary_used_percent=75,
                last_secondary_window_duration_mins=10080,
                last_plan_type="plus",
            ),
        },
    )

    save_registry(path, registry)
    loaded = load_registry(path)
    snapshot = loaded.accounts["plus"].cached_snapshot()

    assert snapshot is not None
    assert snapshot.primary is not None
    assert snapshot.primary.window_duration_mins == 300
    assert snapshot.secondary is not None
    assert snapshot.secondary.window_duration_mins == 10080
