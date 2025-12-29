import json
import os
import tempfile

from datetime import datetime
from typing import Any

from codex_local_conatinerd.prompt_sanitizer import sanitize_prompt


STATE_VERSION = 1


def default_state_path() -> str:
    base = os.path.expanduser("~/.midoriai/codex-container-gui")
    return os.path.join(base, "state.json")


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_str(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"version": STATE_VERSION, "tasks": [], "settings": {}}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        return {"version": STATE_VERSION, "tasks": [], "settings": {}}
    payload.setdefault("version", STATE_VERSION)
    payload.setdefault("tasks", [])
    payload.setdefault("settings", {})
    if not isinstance(payload["tasks"], list):
        payload["tasks"] = []
    if not isinstance(payload["settings"], dict):
        payload["settings"] = {}
    return payload


def save_state(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(payload)
    payload["version"] = STATE_VERSION

    fd, tmp_path = tempfile.mkstemp(prefix="state-", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def serialize_task(task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "image": task.image,
        "host_workdir": task.host_workdir,
        "host_codex_dir": task.host_codex_dir,
        "environment_id": getattr(task, "environment_id", ""),
        "created_at_s": task.created_at_s,
        "status": task.status,
        "exit_code": task.exit_code,
        "error": task.error,
        "container_id": task.container_id,
        "started_at": _dt_to_str(task.started_at),
        "finished_at": _dt_to_str(task.finished_at),
        "logs": list(task.logs[-2000:]),
    }


def deserialize_task(task_cls, data: dict[str, Any]):
    return task_cls(
        task_id=str(data.get("task_id") or ""),
        prompt=sanitize_prompt(str(data.get("prompt") or "")),
        image=str(data.get("image") or ""),
        host_workdir=str(data.get("host_workdir") or ""),
        host_codex_dir=str(data.get("host_codex_dir") or ""),
        environment_id=str(data.get("environment_id") or ""),
        created_at_s=float(data.get("created_at_s") or 0.0),
        status=str(data.get("status") or "queued"),
        exit_code=data.get("exit_code"),
        error=data.get("error"),
        container_id=data.get("container_id"),
        started_at=_dt_from_str(data.get("started_at")),
        finished_at=_dt_from_str(data.get("finished_at")),
        logs=list(data.get("logs") or []),
    )
