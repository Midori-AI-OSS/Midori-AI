from __future__ import annotations

import subprocess

from pathlib import Path

import pytest

from codexd.app_server import read_live_status
from codexd.app_server import StatusReadFailure


def test_app_server_live_read_parses_initialize_account_and_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="\n".join(
                [
                    '{"id":1,"result":{"codexHome":"/tmp/home","platformFamily":"unix","platformOs":"linux","userAgent":"ua"}}',
                    '{"id":2,"result":{"account":{"type":"chatgpt","email":"person@example.com","planType":"team"},"requiresOpenaiAuth":true}}',
                    '{"id":3,"result":{"rateLimits":{"limitId":"codex","planType":"team","primary":{"usedPercent":12,"resetsAt":1},"secondary":{"usedPercent":34,"resetsAt":2}}}}',
                ],
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    snapshot = read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))

    assert snapshot.plan_type == "team"
    assert snapshot.email == "person@example.com"
    assert snapshot.primary is not None
    assert snapshot.primary.used_percent == 12
    assert snapshot.secondary is not None
    assert snapshot.secondary.used_percent == 34


def test_app_server_live_read_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="{not json}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(StatusReadFailure):
        read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))


def test_app_server_live_read_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(StatusReadFailure):
        read_live_status(Path("/tmp/home"), Path("/usr/bin/codex"))
