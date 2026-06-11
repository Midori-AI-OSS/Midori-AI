from __future__ import annotations

from dataclasses import dataclass

from codexd.models import Registry
from codexd.models import StatusReadResult
from codexd.models import AccountRecord
from codexd.models import AccountStatusSnapshot


@dataclass(slots=True)
class RankedCandidate:
    name: str
    source: str
    record: AccountRecord
    snapshot: AccountStatusSnapshot | None
    error: str | None = None


@dataclass(slots=True)
class SelectionDecision:
    name: str
    source: str
    warning: str | None = None
    snapshot: AccountStatusSnapshot | None = None


def rank_accounts(
    registry: Registry,
    live_results: dict[str, StatusReadResult] | None = None,
) -> list[RankedCandidate]:
    candidates: list[RankedCandidate] = []
    for name, record in registry.accounts.items():
        live_result = None if live_results is None else live_results.get(name)
        if live_result is not None and live_result.snapshot is not None:
            candidates.append(
                RankedCandidate(
                    name=name,
                    source=live_result.source,
                    record=record,
                    snapshot=live_result.snapshot,
                    error=live_result.error,
                ),
            )
            continue
        cached_snapshot = record.cached_snapshot()
        if cached_snapshot is not None:
            candidates.append(
                RankedCandidate(
                    name=name,
                    source="cached",
                    record=record,
                    snapshot=cached_snapshot,
                    error=None if live_result is None else live_result.error,
                ),
            )
            continue
        candidates.append(
            RankedCandidate(
                name=name,
                source="unknown",
                record=record,
                snapshot=None,
                error=None if live_result is None else live_result.error,
            ),
        )
    candidates.sort(key=_candidate_sort_key)
    return candidates


def choose_account(
    registry: Registry,
    live_results: dict[str, StatusReadResult] | None = None,
) -> SelectionDecision:
    if not registry.accounts:
        raise RuntimeError("No managed accounts are registered")
    ranked = rank_accounts(registry, live_results)
    if live_results is not None:
        any_live_success = any(
            result.snapshot is not None and result.source == "live"
            for result in live_results.values()
        )
        if not any_live_success and registry.default_account is not None:
            default_record = registry.accounts.get(registry.default_account)
            if default_record is not None:
                return SelectionDecision(
                    name=registry.default_account,
                    source="default-fallback",
                    warning="All live status reads failed; using the configured default account.",
                    snapshot=default_record.cached_snapshot(),
                )
    best = ranked[0]
    warning = None
    if live_results is not None and best.source != "live":
        warning = "No live status was available for the selected account; using cached data."
    return SelectionDecision(
        name=best.name,
        source=best.source,
        warning=warning,
        snapshot=best.snapshot,
    )


def _candidate_sort_key(candidate: RankedCandidate) -> tuple[int, int, int, str, str]:
    source_rank = {
        "live": 0,
        "session_snapshot": 0,
        "cached": 1,
        "unknown": 2,
    }.get(candidate.source, 3)
    primary = 101
    secondary = 101
    if candidate.snapshot is not None and candidate.snapshot.primary is not None:
        primary = candidate.snapshot.primary.used_percent
    if candidate.snapshot is not None and candidate.snapshot.secondary is not None:
        secondary = candidate.snapshot.secondary.used_percent
    oldest_launch = candidate.record.last_successful_launch_at or ""
    return (source_rank, primary, secondary, oldest_launch, candidate.name)
