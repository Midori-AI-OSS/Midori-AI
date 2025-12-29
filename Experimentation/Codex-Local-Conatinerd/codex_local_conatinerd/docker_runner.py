import json
import os
import time
import uuid
import shlex
import tempfile
import selectors
import subprocess

from typing import Any
from typing import Callable

from dataclasses import dataclass
from dataclasses import field
from threading import Event

from codex_local_conatinerd.prompt_sanitizer import sanitize_prompt


@dataclass(frozen=True)
class DockerRunnerConfig:
    task_id: str
    image: str
    host_codex_dir: str
    host_workdir: str
    container_codex_dir: str = "/home/midori-ai/.codex"
    container_workdir: str = "/home/midori-ai/workspace"
    auto_remove: bool = True
    pull_before_run: bool = True
    settings_preflight_script: str | None = None
    environment_preflight_script: str | None = None
    container_settings_preflight_path: str = "/tmp/codex-preflight-settings.sh"
    container_environment_preflight_path: str = "/tmp/codex-preflight-environment.sh"
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    codex_extra_args: list[str] = field(default_factory=list)


def _run_docker(args: list[str], timeout_s: float = 30.0) -> str:
    completed = subprocess.run(
        ["docker", *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout_s,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"docker exited {completed.returncode}"
        raise RuntimeError(detail)
    return (completed.stdout or "").strip()


def _inspect_state(container_id: str) -> dict[str, Any]:
    raw = _run_docker(["inspect", container_id], timeout_s=30.0)
    payload = json.loads(raw)
    if not payload:
        return {}
    return payload[0].get("State") or {}


def _has_image(image: str) -> bool:
    try:
        _run_docker(["image", "inspect", image], timeout_s=10.0)
        return True
    except Exception:
        return False


def _pull_image(image: str) -> None:
    _run_docker(["pull", image], timeout_s=600.0)


def _is_git_repo_root(path: str) -> bool:
    return os.path.exists(os.path.join(path, ".git"))


class DockerPreflightWorker:
    def __init__(
        self,
        config: DockerRunnerConfig,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_done: Callable[[int, str | None], None],
    ) -> None:
        self._config = config
        self._on_state = on_state
        self._on_log = on_log
        self._on_done = on_done
        self._stop = Event()
        self._container_id: str | None = None

    @property
    def container_id(self) -> str | None:
        return self._container_id

    def request_stop(self) -> None:
        self._stop.set()
        if self._container_id:
            try:
                _run_docker(["stop", "-t", "1", self._container_id], timeout_s=10.0)
            except Exception:
                try:
                    _run_docker(["kill", self._container_id], timeout_s=10.0)
                except Exception:
                    pass

    def run(self) -> None:
        preflight_tmp_paths: list[str] = []
        try:
            os.makedirs(self._config.host_codex_dir, exist_ok=True)
            container_name = f"codex-preflight-{uuid.uuid4().hex[:10]}"

            def _write_preflight_script(script: str, label: str) -> str:
                fd, tmp_path = tempfile.mkstemp(
                    prefix=f"codex-preflight-{label}-{self._config.task_id or 'task'}-",
                    suffix=".sh",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        if not script.endswith("\n"):
                            script += "\n"
                        f.write(script)
                except Exception:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    raise
                preflight_tmp_paths.append(tmp_path)
                return tmp_path

            settings_preflight_tmp_path: str | None = None
            if (self._config.settings_preflight_script or "").strip():
                settings_preflight_tmp_path = _write_preflight_script(
                    str(self._config.settings_preflight_script or ""),
                    "settings",
                )

            environment_preflight_tmp_path: str | None = None
            if (self._config.environment_preflight_script or "").strip():
                environment_preflight_tmp_path = _write_preflight_script(
                    str(self._config.environment_preflight_script or ""),
                    "environment",
                )

            if self._config.pull_before_run:
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] docker pull {self._config.image}")
                _pull_image(self._config.image)
                self._on_log("[host] pull complete")
            elif not _has_image(self._config.image):
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] image missing; docker pull {self._config.image}")
                _pull_image(self._config.image)
                self._on_log("[host] pull complete")

            preflight_clause = ""
            preflight_mounts: list[str] = []
            if settings_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] settings preflight enabled; mounting -> {self._config.container_settings_preflight_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{settings_preflight_tmp_path}:{self._config.container_settings_preflight_path}:ro",
                    ]
                )
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS={shlex.quote(self._config.container_settings_preflight_path)}; '
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if environment_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] environment preflight enabled; mounting -> {self._config.container_environment_preflight_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{environment_preflight_tmp_path}:{self._config.container_environment_preflight_path}:ro",
                    ]
                )
                preflight_clause += (
                    f'PREFLIGHT_ENV={shlex.quote(self._config.container_environment_preflight_path)}; '
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )

            env_args: list[str] = []
            for key, value in sorted((self._config.env_vars or {}).items()):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            extra_mount_args: list[str] = []
            for mount in (self._config.extra_mounts or []):
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])

            args = [
                "run",
                "-d",
                "-t",
                "--name",
                container_name,
                "-v",
                f"{self._config.host_codex_dir}:{self._config.container_codex_dir}",
                "-v",
                f"{self._config.host_workdir}:{self._config.container_workdir}",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                "-w",
                self._config.container_workdir,
                self._config.image,
                "/bin/bash",
                "-lc",
                "set -euo pipefail; "
                f"{preflight_clause}"
                'echo "[preflight] complete"; ',
            ]
            self._container_id = _run_docker(args, timeout_s=60.0)
            try:
                self._on_state(_inspect_state(self._container_id))
            except Exception:
                pass

            logs_proc = subprocess.Popen(
                ["docker", "logs", "-f", "--timestamps", self._container_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            selector = selectors.DefaultSelector()
            if logs_proc.stdout:
                selector.register(logs_proc.stdout, selectors.EVENT_READ)

            last_poll = 0.0
            try:
                while not self._stop.is_set():
                    now = time.time()
                    if now - last_poll >= 0.75:
                        last_poll = now
                        try:
                            state = _inspect_state(self._container_id)
                        except Exception:
                            state = {}
                        if state:
                            self._on_state(state)
                        status = (state.get("Status") or "").lower()
                        if status in {"exited", "dead"}:
                            break

                    if logs_proc.poll() is not None:
                        time.sleep(0.05)
                        continue

                    for key, _ in selector.select(timeout=0.05):
                        try:
                            chunk = key.fileobj.readline()
                        except Exception:
                            chunk = ""
                        if chunk:
                            self._on_log(chunk.rstrip("\n"))
            finally:
                if logs_proc.poll() is None:
                    logs_proc.terminate()
                    try:
                        logs_proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        logs_proc.kill()

            try:
                final_state = _inspect_state(self._container_id)
            except Exception:
                final_state = {}
            self._on_state(final_state)
            exit_code = int(final_state.get("ExitCode") or 0)

            if self._config.auto_remove:
                try:
                    _run_docker(["rm", "-f", self._container_id], timeout_s=30.0)
                except Exception:
                    pass

            self._on_done(exit_code, None)
        except Exception as exc:
            self._on_done(1, str(exc))
        finally:
            for tmp_path in preflight_tmp_paths:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass


class DockerCodexWorker:
    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_done: Callable[[int, str | None], None],
    ) -> None:
        self._config = config
        self._prompt = sanitize_prompt((prompt or "").strip())
        self._on_state = on_state
        self._on_log = on_log
        self._on_done = on_done
        self._stop = Event()
        self._container_id: str | None = None

    @property
    def container_id(self) -> str | None:
        return self._container_id

    def request_stop(self) -> None:
        self._stop.set()
        if self._container_id:
            try:
                _run_docker(["stop", "-t", "1", self._container_id], timeout_s=10.0)
            except Exception:
                try:
                    _run_docker(["kill", self._container_id], timeout_s=10.0)
                except Exception:
                    pass

    def run(self) -> None:
        preflight_tmp_paths: list[str] = []
        try:
            os.makedirs(self._config.host_codex_dir, exist_ok=True)
            container_name = f"codex-gui-{uuid.uuid4().hex[:10]}"

            def _write_preflight_script(script: str, label: str) -> str:
                fd, tmp_path = tempfile.mkstemp(
                    prefix=f"codex-preflight-{label}-{self._config.task_id or 'task'}-",
                    suffix=".sh",
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        if not script.endswith("\n"):
                            script += "\n"
                        f.write(script)
                except Exception:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    raise
                preflight_tmp_paths.append(tmp_path)
                return tmp_path

            settings_preflight_tmp_path: str | None = None
            if (self._config.settings_preflight_script or "").strip():
                settings_preflight_tmp_path = _write_preflight_script(
                    str(self._config.settings_preflight_script or ""),
                    "settings",
                )

            environment_preflight_tmp_path: str | None = None
            if (self._config.environment_preflight_script or "").strip():
                environment_preflight_tmp_path = _write_preflight_script(
                    str(self._config.environment_preflight_script or ""),
                    "environment",
                )

            if self._config.pull_before_run:
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] docker pull {self._config.image}")
                _pull_image(self._config.image)
                self._on_log("[host] pull complete")
            elif not _has_image(self._config.image):
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] image missing; docker pull {self._config.image}")
                _pull_image(self._config.image)
                self._on_log("[host] pull complete")

            codex_args = [
                "codex",
                "exec",
                "--sandbox",
                "danger-full-access",
            ]
            if not _is_git_repo_root(self._config.host_workdir):
                codex_args.append("--skip-git-repo-check")
                self._on_log("[host] .git missing in workdir; adding --skip-git-repo-check")
            if self._config.codex_extra_args:
                codex_args.extend(self._config.codex_extra_args)
            codex_args.append(self._prompt)

            codex_cmd = " ".join(shlex.quote(part) for part in codex_args)
            preflight_clause = ""
            preflight_mounts: list[str] = []
            if settings_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] settings preflight enabled; mounting -> {self._config.container_settings_preflight_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{settings_preflight_tmp_path}:{self._config.container_settings_preflight_path}:ro",
                    ]
                )
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS={shlex.quote(self._config.container_settings_preflight_path)}; '
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if environment_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] environment preflight enabled; mounting -> {self._config.container_environment_preflight_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{environment_preflight_tmp_path}:{self._config.container_environment_preflight_path}:ro",
                    ]
                )
                preflight_clause += (
                    f'PREFLIGHT_ENV={shlex.quote(self._config.container_environment_preflight_path)}; '
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )

            env_args: list[str] = []
            for key, value in sorted((self._config.env_vars or {}).items()):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            extra_mount_args: list[str] = []
            for mount in (self._config.extra_mounts or []):
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            args = [
                "run",
                "-d",
                "-t",
                "--name",
                container_name,
                "-v",
                f"{self._config.host_codex_dir}:{self._config.container_codex_dir}",
                "-v",
                f"{self._config.host_workdir}:{self._config.container_workdir}",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                "-w",
                self._config.container_workdir,
                self._config.image,
                "/bin/bash",
                "-lc",
                "set -euo pipefail; "
                f"{preflight_clause}"
                "command -v codex >/dev/null 2>&1 || { "
                "echo \"codex not found in PATH=$PATH\"; exit 127; "
                "}; "
                f"exec {codex_cmd}",
            ]
            self._container_id = _run_docker(args, timeout_s=60.0)
            try:
                self._on_state(_inspect_state(self._container_id))
            except Exception:
                pass

            logs_proc = subprocess.Popen(
                ["docker", "logs", "-f", "--timestamps", self._container_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            selector = selectors.DefaultSelector()
            if logs_proc.stdout:
                selector.register(logs_proc.stdout, selectors.EVENT_READ)

            last_poll = 0.0
            try:
                while not self._stop.is_set():
                    now = time.time()
                    if now - last_poll >= 0.75:
                        last_poll = now
                        try:
                            state = _inspect_state(self._container_id)
                        except Exception:
                            state = {}
                        if state:
                            self._on_state(state)
                        status = (state.get("Status") or "").lower()
                        if status in {"exited", "dead"}:
                            break

                    if logs_proc.poll() is not None:
                        time.sleep(0.05)
                        continue

                    for key, _ in selector.select(timeout=0.05):
                        try:
                            chunk = key.fileobj.readline()
                        except Exception:
                            chunk = ""
                        if chunk:
                            self._on_log(chunk.rstrip("\n"))
            finally:
                if logs_proc.poll() is None:
                    logs_proc.terminate()
                    try:
                        logs_proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        logs_proc.kill()

            try:
                final_state = _inspect_state(self._container_id)
            except Exception:
                final_state = {}
            self._on_state(final_state)
            exit_code = int(final_state.get("ExitCode") or 0)

            if self._config.auto_remove:
                try:
                    _run_docker(["rm", "-f", self._container_id], timeout_s=30.0)
                except Exception:
                    pass

            self._on_done(exit_code, None)
        except Exception as exc:
            self._on_done(1, str(exc))
        finally:
            for tmp_path in preflight_tmp_paths:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
