from __future__ import annotations

from pathlib import Path

from codexd.importer import should_exclude


def test_import_exclusions_cover_transient_runtime_files() -> None:
    assert should_exclude(Path("goals_1.sqlite-wal"), is_dir=False)
    assert should_exclude(Path("session-state"), is_dir=True)
    assert should_exclude(Path(".tmp/arg0-helper"), is_dir=True)
    assert not should_exclude(Path("config.toml"), is_dir=False)
    assert not should_exclude(Path("sessions"), is_dir=True)
