from __future__ import annotations

import cProfile
import pstats
import time

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProfileSession:
    profile: cProfile.Profile
    started_at: float
    seconds: float
    out_path: Path


class ProfilerController:
    def __init__(self) -> None:
        self._session: ProfileSession | None = None

    def start(self, *, seconds: float, out_path: Path) -> None:
        if self._session is not None:
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)
        prof = cProfile.Profile()
        prof.enable()
        self._session = ProfileSession(profile=prof, started_at=time.perf_counter(), seconds=float(seconds), out_path=out_path)

    def stop_if_due(self) -> Path | None:
        if self._session is None:
            return None
        elapsed = time.perf_counter() - self._session.started_at
        if elapsed < self._session.seconds:
            return None
        self._session.profile.disable()
        self._session.profile.dump_stats(str(self._session.out_path))
        stats = pstats.Stats(self._session.profile).sort_stats("tottime")
        stats.print_stats(25)
        out = self._session.out_path
        self._session = None
        return out
