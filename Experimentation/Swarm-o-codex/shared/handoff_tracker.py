from __future__ import annotations

from typing import Iterable
from dataclasses import field
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class HandoffTracker:
    """Tracks handoffs per agent and reports unmet role requirements."""

    required_counts: dict[str, int]
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))  # type: ignore[arg-type]
    history: list[tuple[str, str]] = field(default_factory=list)

    def record(self, source_agent: str, target_agent: str) -> None:
        """Record a completed handoff event."""
        self.counts[source_agent] += 1
        self.history.append((source_agent, target_agent))

    def iter_missing(self) -> Iterable[str]:
        """Yield human-friendly reminders for unmet requirements."""
        for role, required in self.required_counts.items():
            completed = self.counts.get(role, 0)
            if completed < required:
                remaining = required - completed
                plural = "s" if remaining != 1 else ""
                yield f"{remaining} more {role} handoff{plural} needed (have {completed} of {required})."

    def requirements_met(self) -> bool:
        """Return True if all required role handoffs have been completed."""
        return not any(True for _ in self.iter_missing())

