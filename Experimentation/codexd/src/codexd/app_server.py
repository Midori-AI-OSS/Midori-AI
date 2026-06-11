from __future__ import annotations

import json
import os
import subprocess

from pathlib import Path

from codexd.models import AccountStatusSnapshot


class StatusReadFailure(RuntimeError):
    pass


def read_live_status(
    codex_home: Path,
    codex_bin: Path,
    timeout_seconds: int = 8,
) -> AccountStatusSnapshot:
    payload = _build_request_payload()
    env = _status_env(codex_home)
    try:
        completed = subprocess.run(
            [str(codex_bin), "app-server", "--listen", "stdio://"],
            capture_output=True,
            check=False,
            env=env,
            input=payload,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise StatusReadFailure(
            f"Timed out reading app-server status for {codex_home}",
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise StatusReadFailure(
            f"codex app-server exited with {completed.returncode}: {stderr or 'no stderr'}",
        )

    responses = _parse_responses(completed.stdout)
    if 1 not in responses:
        raise StatusReadFailure("App-server did not return initialize response")
    if 2 not in responses:
        raise StatusReadFailure("App-server did not return account/read response")
    if 3 not in responses:
        raise StatusReadFailure("App-server did not return account/rateLimits/read response")
    return AccountStatusSnapshot.from_api(responses[2], responses[3])


def _build_request_payload() -> str:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "codexd",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "initialized",
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "account/read",
            "params": {
                "refreshToken": True,
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "account/rateLimits/read",
            "params": None,
        },
    ]
    return "".join(json.dumps(message, separators=(",", ":")) + "\n" for message in messages)


def _parse_responses(stdout: str) -> dict[int, dict[str, object]]:
    responses: dict[int, dict[str, object]] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StatusReadFailure(f"Malformed app-server JSON: {exc}") from exc
        if not isinstance(message, dict):
            continue
        if "error" in message:
            raise StatusReadFailure(f"App-server returned error payload: {line}")
        message_id = message.get("id")
        result = message.get("result")
        if isinstance(message_id, int) and isinstance(result, dict):
            responses[message_id] = result
    return responses


def _status_env(codex_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["CODEX_HOME"] = str(codex_home)
    return env
