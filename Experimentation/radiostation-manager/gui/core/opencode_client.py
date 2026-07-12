from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class OpenCodeWorker(QThread):
    progress_update = Signal(int, int, str)
    reasoning_update = Signal(str)
    finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        prompt: str,
        working_dir: Path,
        model: str = "lm-studio/qwen/qwen3.6-27b",
        variant: str = "xhigh",
        continue_session: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._prompt = prompt
        self._working_dir = working_dir
        self._model = model
        self._variant = variant
        self._continue = continue_session
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.requestInterruption()

    def run(self):
        output_file = tempfile.mktemp(suffix=".jsonl", prefix="opencode-")
        try:
            cmd = [
                "opencode",
                "run",
                "--dir",
                str(self._working_dir),
                "--variant",
                self._variant,
                "-m",
                self._model,
                "--thinking",
                "--format",
                "json",
            ]
            if self._continue:
                cmd.append("-c")
            cmd.append(self._prompt)

            self.progress_update.emit(0, 100, "Starting...")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.stdout is not None and proc.stderr is not None

            full_text = ""
            partial_text = ""
            line_count = 0

            while True:
                if self._cancelled or self.isInterruptionRequested():
                    proc.terminate()
                    self.finished.emit(full_text if full_text else partial_text)
                    return

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if not line:
                    continue

                line = line.strip()
                if not line:
                    continue

                line_count += 1
                if line_count % 5 == 0:
                    self.progress_update.emit(
                        min(line_count * 2, 90), 100, "Thinking..."
                    )

                try:
                    data = json.loads(line)
                    msg_type = data.get("type", "")
                    text = data.get("part", {}).get("text", "")
                    if msg_type == "text" and text:
                        full_text = text
                        partial_text = text
                    if msg_type == "reasoning" and text:
                        clean = re.sub(r"<think>|</think>", "", text).strip()
                        if clean:
                            self.reasoning_update.emit(clean[:200])
                except (json.JSONDecodeError, KeyError):
                    pass

            proc.wait()
            try:
                stderr_output = proc.stderr.read() if proc.stderr else ""
            except Exception:
                stderr_output = ""

            if proc.returncode != 0:
                self.error_occurred.emit(
                    stderr_output or f"OpenCode exited with code {proc.returncode}"
                )
                return

            final = re.sub(
                r"<think>.*?</think>", "", full_text or partial_text, flags=re.DOTALL
            ).strip()
            self.progress_update.emit(100, 100, "Done.")
            self.finished.emit(final)

        except FileNotFoundError:
            self.error_occurred.emit("opencode not found in PATH")
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            Path(output_file).unlink(missing_ok=True)
