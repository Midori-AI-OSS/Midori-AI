from __future__ import annotations

from codexd.models import Registry
from codexd.models import StatusReadResult
from codexd.models import AccountRecord
from codexd.models import RateLimitWindow
from codexd.models import AccountStatusSnapshot
from codexd.ranking import choose_account
from codexd.ranking import rank_accounts


def test_rank_accounts_prefers_lower_usage_and_oldest_launch() -> None:
    registry = Registry(
        default_account="beta",
        accounts={
            "alpha": AccountRecord(
                name="alpha",
                home_path="/tmp/a",
                created_at="2026-06-10T00:00:00Z",
                last_successful_launch_at="2026-06-10T05:00:00Z",
            ),
            "beta": AccountRecord(
                name="beta",
                home_path="/tmp/b",
                created_at="2026-06-10T00:00:00Z",
                last_successful_launch_at="2026-06-10T06:00:00Z",
            ),
        },
    )
    live_results = {
        "alpha": StatusReadResult(
            source="live",
            snapshot=AccountStatusSnapshot(
                primary=RateLimitWindow(used_percent=20),
                secondary=RateLimitWindow(used_percent=10),
            ),
        ),
        "beta": StatusReadResult(
            source="live",
            snapshot=AccountStatusSnapshot(
                primary=RateLimitWindow(used_percent=20),
                secondary=RateLimitWindow(used_percent=10),
            ),
        ),
    }

    ranked = rank_accounts(registry, live_results)

    assert [candidate.name for candidate in ranked] == ["alpha", "beta"]


def test_choose_account_uses_default_when_all_live_reads_fail() -> None:
    registry = Registry(
        default_account="beta",
        accounts={
            "alpha": AccountRecord(
                name="alpha",
                home_path="/tmp/a",
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=10,
            ),
            "beta": AccountRecord(
                name="beta",
                home_path="/tmp/b",
                created_at="2026-06-10T00:00:00Z",
                last_primary_used_percent=99,
            ),
        },
    )
    live_results = {
        "alpha": StatusReadResult(source="error", error="boom"),
        "beta": StatusReadResult(source="error", error="boom"),
    }

    decision = choose_account(registry, live_results)

    assert decision.name == "beta"
    assert decision.source == "default-fallback"
