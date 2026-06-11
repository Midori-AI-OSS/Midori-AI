from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time

from pathlib import Path

from codexd.models import AccountStatusSnapshot


ACCOUNT_RESPONSE_GRACE_SECONDS = 0.5
REQUEST_WRITE_DELAY_SECONDS = 0.1


class StatusReadFailure(RuntimeError):
    pass


def read_live_status(
    codex_home: Path,
    codex_bin: Path,
    timeout_seconds: int = 8,
) -> AccountStatusSnapshot:
    env = _status_env(codex_home)
    process = subprocess.Popen(
        [str(codex_bin), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_queue: queue.Queue[str] = queue.Queue()
    stderr_queue: queue.Queue[str] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_read_stream_lines,
        args=(process.stdout, stdout_queue),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_stream_lines,
        args=(process.stderr, stderr_queue),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        _write_requests(process)
        responses = _collect_responses(process, stdout_queue, stderr_queue, timeout_seconds)
    finally:
        _shutdown_process(process)
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

    if 1 not in responses:
        raise StatusReadFailure("App-server did not return initialize response")
    rate_limit_payload = responses.get(3)
    if rate_limit_payload is None:
        raise StatusReadFailure("App-server did not return account/rateLimits/read response")
    snapshot = AccountStatusSnapshot.from_api(responses.get(2), rate_limit_payload)
    if not snapshot.has_usable_status():
        raise StatusReadFailure("App-server returned unusable rate-limit status data")
    return snapshot


def _build_request_payloads() -> list[dict[str, object]]:
    return [
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


def _write_requests(process: subprocess.Popen[str]) -> None:
    if process.stdin is None:
        raise StatusReadFailure("App-server stdin was not available")
    for payload in _build_request_payloads():
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()
        time.sleep(REQUEST_WRITE_DELAY_SECONDS)


def _collect_responses(
    process: subprocess.Popen[str],
    stdout_queue: queue.Queue[str],
    stderr_queue: queue.Queue[str],
    timeout_seconds: int,
) -> dict[int, dict[str, object]]:
    deadline = time.monotonic() + timeout_seconds
    grace_deadline: float | None = None
    responses: dict[int, dict[str, object]] = {}
    stderr_lines: list[str] = []

    while True:
        if 1 in responses and 3 in responses and grace_deadline is None:
            grace_deadline = time.monotonic() + ACCOUNT_RESPONSE_GRACE_SECONDS
        if 1 in responses and 2 in responses and 3 in responses:
            break

        now = time.monotonic()
        stop_at = deadline if grace_deadline is None else min(deadline, grace_deadline)
        remaining = stop_at - now
        if remaining <= 0:
            break

        try:
            line = stdout_queue.get(timeout=remaining)
        except queue.Empty:
            break

        _drain_queue(stderr_queue, stderr_lines)
        message = _parse_message(line)
        if "error" in message:
            stderr_hint = _format_stderr(stderr_lines)
            detail = f"App-server returned error payload: {line.strip()}"
            if stderr_hint:
                detail = f"{detail} | stderr: {stderr_hint}"
            raise StatusReadFailure(detail)
        message_id = message.get("id")
        result = message.get("result")
        if isinstance(message_id, int) and isinstance(result, dict):
            responses[message_id] = result

    _drain_queue(stderr_queue, stderr_lines)
    if not responses:
        stderr_hint = _format_stderr(stderr_lines)
        if stderr_hint:
            raise StatusReadFailure(f"App-server returned no usable responses. stderr: {stderr_hint}")
    return responses


def _parse_message(line: str) -> dict[str, object]:
    raw = line.strip()
    if not raw:
        return {}
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StatusReadFailure(f"Malformed app-server JSON: {exc}") from exc
    if not isinstance(message, dict):
        return {}
    return message


def _read_stream_lines(stream, sink: queue.Queue[str]) -> None:
    if stream is None:
        return
    while True:
        line = stream.readline()
        if not line:
            break
        sink.put(line)


def _drain_queue(source: queue.Queue[str], sink: list[str]) -> None:
    while True:
        try:
            sink.append(source.get_nowait().rstrip())
        except queue.Empty:
            return


def _shutdown_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)


def _format_stderr(lines: list[str]) -> str:
    filtered = [line for line in lines if line]
    return " | ".join(filtered[-3:])


def _status_env(codex_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["CODEX_HOME"] = str(codex_home)
    return env
