import json
import os
import tempfile

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from codex_local_conatinerd.persistence import default_state_path


ENVIRONMENT_VERSION = 1
ENVIRONMENT_FILENAME_PREFIX = "environment-"

ALLOWED_STAINS = ("slate", "cyan", "emerald", "violet", "rose", "amber")


def default_data_dir() -> str:
    return os.path.dirname(default_state_path())


def environment_path(env_id: str, data_dir: str | None = None) -> str:
    data_dir = data_dir or default_data_dir()
    safe = "".join(ch for ch in (env_id or "").strip() if ch.isalnum() or ch in {"-", "_"})
    if not safe:
        safe = "default"
    return os.path.join(data_dir, f"{ENVIRONMENT_FILENAME_PREFIX}{safe}.json")


@dataclass
class Environment:
    env_id: str
    name: str
    color: str = "emerald"
    host_workdir: str = ""
    host_codex_dir: str = ""
    codex_extra_args: str = ""
    preflight_enabled: bool = False
    preflight_script: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)

    def normalized_color(self) -> str:
        value = (self.color or "").strip().lower()
        return value if value in ALLOWED_STAINS else "slate"


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="env-", suffix=".json", dir=os.path.dirname(path))
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


def _environment_from_payload(payload: dict[str, Any]) -> Environment | None:
    if not isinstance(payload, dict):
        return None
    version = int(payload.get("version") or ENVIRONMENT_VERSION)
    if version != ENVIRONMENT_VERSION:
        return None
    env_id = str(payload.get("env_id") or payload.get("id") or "").strip()
    if not env_id:
        return None
    name = str(payload.get("name") or env_id).strip()
    color = str(payload.get("color") or "slate").strip().lower()
    host_workdir = str(payload.get("host_workdir") or "").strip()
    host_codex_dir = str(payload.get("host_codex_dir") or "").strip()
    codex_extra_args = str(payload.get("codex_extra_args") or "").strip()
    preflight_enabled = bool(payload.get("preflight_enabled") or False)
    preflight_script = str(payload.get("preflight_script") or "")
    env_vars = payload.get("env_vars") or {}
    if not isinstance(env_vars, dict):
        env_vars = {}
    extra_mounts = payload.get("extra_mounts") or []
    if not isinstance(extra_mounts, list):
        extra_mounts = []
    env = Environment(
        env_id=env_id,
        name=name or env_id,
        color=color,
        host_workdir=host_workdir,
        host_codex_dir=host_codex_dir,
        codex_extra_args=codex_extra_args,
        preflight_enabled=preflight_enabled,
        preflight_script=preflight_script,
        env_vars={str(k): str(v) for k, v in env_vars.items() if str(k).strip()},
        extra_mounts=[str(item) for item in extra_mounts if str(item).strip()],
    )
    env.color = env.normalized_color()
    return env


def load_environments(data_dir: str | None = None) -> dict[str, Environment]:
    data_dir = data_dir or default_data_dir()
    if not os.path.isdir(data_dir):
        return {}
    envs: dict[str, Environment] = {}
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith(ENVIRONMENT_FILENAME_PREFIX) or not name.endswith(".json"):
            continue
        path = os.path.join(data_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        env = _environment_from_payload(payload)
        if env is None:
            continue
        envs[env.env_id] = env
    return envs


def save_environment(env: Environment, data_dir: str | None = None) -> None:
    path = environment_path(env.env_id, data_dir=data_dir)
    payload: dict[str, Any] = {
        "version": ENVIRONMENT_VERSION,
        "env_id": env.env_id,
        "name": env.name,
        "color": env.normalized_color(),
        "host_workdir": env.host_workdir,
        "host_codex_dir": env.host_codex_dir,
        "codex_extra_args": env.codex_extra_args,
        "preflight_enabled": bool(env.preflight_enabled),
        "preflight_script": env.preflight_script,
        "env_vars": dict(env.env_vars),
        "extra_mounts": list(env.extra_mounts),
    }
    _atomic_write_json(path, payload)


def delete_environment(env_id: str, data_dir: str | None = None) -> None:
    path = environment_path(env_id, data_dir=data_dir)
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def parse_env_vars_text(text: str) -> tuple[dict[str, str], list[str]]:
    parsed: dict[str, str] = {}
    errors: list[str] = []
    for idx, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line {idx}: missing '='")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            errors.append(f"line {idx}: empty key")
            continue
        parsed[key] = value
    return parsed, errors


def parse_mounts_text(text: str) -> list[str]:
    mounts: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        mounts.append(line)
    return mounts
