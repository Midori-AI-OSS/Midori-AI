from __future__ import annotations

import subprocess
import time

from pathlib import Path

import pytest

from codexd.app_server import read_live_status
from codexd.app_server import StatusReadFailure


def test_app_server_live_read_parses_initialize_account_and_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}\n',
                '{"id":2,"result":{"account":{"type":"chatgpt","email":"person@example.com","planType":"team"},"requiresOpenaiAuth":true}}\n',
                '{"id":3,"result":{"rateLimits":{"limitId":"codex","planType":"team","primary":{"usedPercent":12,"resetsAt":1},"secondary":{"usedPercent":34,"resetsAt":2}}}}\n',
            ],
        ),
    )
    snapshot = read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))

    assert snapshot.plan_type == "team"
    assert snapshot.email == "person@example.com"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 12
    assert snapshot.secondary is not None
    assert snapshot.secondary.used_percent == 34


def test_app_server_live_read_launches_with_per_account_codex_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_popen(*args, **kwargs):
        recorded["env"] = kwargs.get("env")
        return FakeProcess(
            stdout_lines=[
                '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}\n',
                '{"id":3,"result":{"rateLimits":{"limitId":"codex","planType":"team","primary":{"usedPercent":12,"resetsAt":1}}}}\n',
            ],
        )

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    read_live_status(Path("/tmp/per-account-home"), Path("/usr/bin/codex"))

    assert isinstance(recorded["env"], dict)
    assert recorded["env"]["CODEX_HOME"] == "/tmp/per-account-home"


def test_app_server_live_read_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(stdout_lines=["{not json}\n"]),
    )

    with pytest.raises(StatusReadFailure):
        read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))


def test_app_server_live_read_times_out_when_no_usable_rate_limits_arrive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}\n',
            ],
            stdout_delay=0.2,
        ),
    )

    with pytest.raises(StatusReadFailure):
        read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"), timeout_seconds=0.05)


def test_app_server_live_read_accepts_out_of_order_and_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}\n',
                '{"method":"remoteControl/status/changed","params":{"status":"disabled"}}\n',
                '{"id":3,"result":{"rateLimits":{"limitId":"codex","planType":"team","primary":{"usedPercent":21,"resetsAt":7}}}}\n',
                '{"id":2,"result":{"account":{"type":"chatgpt","email":"person@example.com","planType":"team"},"requiresOpenaiAuth":true}}\n',
            ],
        ),
    )

    snapshot = read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))

    assert snapshot.email == "person@example.com"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 21


def test_app_server_live_read_allows_rate_limits_without_account_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}\n',
                '{"id":3,"result":{"rateLimits":{"limitId":"codex","planType":"team","primary":{"usedPercent":7,"resetsAt":9}}}}\n',
            ],
        ),
    )

    snapshot = read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))

    assert snapshot.email is None
    assert snapshot.account_type is None
    assert snapshot.plan_type == "team"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 7


class FakeProcess:
    def __init__(
        self,
        stdout_lines: list[str],
        stderr_lines: list[str] | None = None,
        stdout_delay: float = 0.0,
    ) -> None:
        self.stdin = FakeInput()
        self.stdout = FakeStream(stdout_lines, delay=stdout_delay)
        self.stderr = FakeStream(stderr_lines or [])
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9


class FakeInput:
    def __init__(self) -> None:
        self.closed = False
        self.writes: list[str] = []

    def write(self, payload: str) -> int:
        self.writes.append(payload)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeStream:
    def __init__(self, lines: list[str], delay: float = 0.0) -> None:
        self._lines = iter(lines)
        self._delay = delay

    def readline(self) -> str:
        if self._delay:
            time.sleep(self._delay)
        try:
            return next(self._lines)
        except StopIteration:
            return ""

    def close(self) -> None:
        return None
