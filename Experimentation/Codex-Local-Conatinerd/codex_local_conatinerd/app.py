import os
import sys
import time
import shutil
import shlex

from pathlib import Path
from uuid import uuid4
from datetime import datetime
from datetime import timezone
from dataclasses import dataclass
from dataclasses import field

from PySide6.QtCore import QObject
from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QIcon
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from codex_local_conatinerd.docker_runner import DockerCodexWorker
from codex_local_conatinerd.docker_runner import DockerPreflightWorker
from codex_local_conatinerd.docker_runner import DockerRunnerConfig
from codex_local_conatinerd.environments import ALLOWED_STAINS
from codex_local_conatinerd.environments import Environment
from codex_local_conatinerd.environments import delete_environment
from codex_local_conatinerd.environments import load_environments
from codex_local_conatinerd.environments import parse_env_vars_text
from codex_local_conatinerd.environments import parse_mounts_text
from codex_local_conatinerd.environments import save_environment
from codex_local_conatinerd.persistence import default_state_path
from codex_local_conatinerd.persistence import deserialize_task
from codex_local_conatinerd.persistence import load_state
from codex_local_conatinerd.persistence import save_state
from codex_local_conatinerd.persistence import serialize_task
from codex_local_conatinerd.prompt_sanitizer import sanitize_prompt
from codex_local_conatinerd.log_format import parse_docker_datetime
from codex_local_conatinerd.log_format import prettify_log_line
from codex_local_conatinerd.style import app_stylesheet
from codex_local_conatinerd.widgets import GlassCard
from codex_local_conatinerd.widgets import LogHighlighter
from codex_local_conatinerd.widgets import StatusGlyph


PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"
APP_TITLE = "Midori AI Agents Runner"


def _app_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().with_name("midoriai-logo.png")
    if not icon_path.exists():
        return None
    return QIcon(str(icon_path))


def _parse_docker_time(value: str | None) -> datetime | None:
    dt = parse_docker_datetime(value)
    if dt is None:
        return None
    # Docker reports Go's "zero time" for fields like FinishedAt while running:
    # "0001-01-01T00:00:00Z". Treat anything pre-epoch as unset.
    if dt.year < 1970:
        return None
    return dt


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    if minutes < 60:
        return f"{minutes}m {int(rem)}s"
    hours = int(minutes // 60)
    minutes = minutes - hours * 60
    return f"{hours}h {minutes}m"


def _status_color(status: str) -> QColor:
    key = (status or "").lower()
    if key in {"pulling"}:
        return QColor(56, 189, 248, 220)
    if key in {"done"}:
        return QColor(16, 185, 129, 230)
    if key in {"failed"}:
        return QColor(244, 63, 94, 230)
    if key in {"created"}:
        return QColor(148, 163, 184, 220)
    if key in {"running"}:
        return QColor(16, 185, 129, 220)
    if key in {"paused"}:
        return QColor(245, 158, 11, 220)
    if key in {"restarting", "removing"}:
        return QColor(56, 189, 248, 220)
    if key in {"exited", "dead"}:
        return QColor(148, 163, 184, 220)
    if key in {"error"}:
        return QColor(244, 63, 94, 220)
    return QColor(148, 163, 184, 220)


def _rgba(color: QColor, alpha: int | None = None) -> str:
    a = int(color.alpha()) if alpha is None else int(alpha)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {a})"


def _stain_color(stain: str) -> QColor:
    key = (stain or "").strip().lower()
    if key == "cyan":
        return QColor(56, 189, 248, 220)
    if key == "emerald":
        return QColor(16, 185, 129, 220)
    if key == "violet":
        return QColor(139, 92, 246, 220)
    if key == "rose":
        return QColor(244, 63, 94, 220)
    if key == "amber":
        return QColor(245, 158, 11, 220)
    return QColor(148, 163, 184, 220)


class GlassRoot(QWidget):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(10, 12, 18))

        w = max(1, self.width())
        h = max(1, self.height())
        shards = [
            (QColor(56, 189, 248, 38), [(0.00, 0.10), (0.38, 0.00), (0.55, 0.23), (0.22, 0.34)]),
            (QColor(16, 185, 129, 34), [(0.62, 0.00), (1.00, 0.14), (0.88, 0.42), (0.58, 0.28)]),
            (QColor(139, 92, 246, 28), [(0.08, 0.48), (0.28, 0.38), (0.52, 0.64), (0.20, 0.80)]),
            (QColor(244, 63, 94, 22), [(0.62, 0.56), (0.94, 0.46), (1.00, 0.82), (0.76, 1.00)]),
            (QColor(245, 158, 11, 18), [(0.00, 0.78), (0.20, 0.64), (0.40, 1.00), (0.00, 1.00)]),
        ]

        for color, points in shards:
            path = QPainterPath()
            x0, y0 = points[0]
            path.moveTo(int(x0 * w), int(y0 * h))
            for x, y in points[1:]:
                path.lineTo(int(x * w), int(y * h))
            path.closeSubpath()
            painter.fillPath(path, color)
            painter.setPen(QColor(255, 255, 255, 10))
            painter.drawPath(path)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def setFullText(self, text: str) -> None:
        self._full_text = text
        self._update_elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, max(10, self.width() - 4))
        super().setText(elided)


@dataclass
class Task:
    task_id: str
    prompt: str
    image: str
    host_workdir: str
    host_codex_dir: str
    created_at_s: float
    environment_id: str = ""
    status: str = "queued"
    exit_code: int | None = None
    error: str | None = None
    container_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    logs: list[str] = field(default_factory=list)

    def elapsed_seconds(self, now_s: float | None = None) -> float | None:
        created_s = float(self.created_at_s or 0.0)
        if created_s <= 0.0:
            if self.started_at and self.finished_at and self.finished_at > self.started_at:
                return (self.finished_at - self.started_at).total_seconds()
            return None
        finished = self.finished_at
        if finished is not None and finished.year < 1970:
            finished = None
        if finished is not None:
            try:
                end_s = float(finished.timestamp())
            except Exception:
                end_s = float(now_s if now_s is not None else time.time())
        else:
            end_s = float(now_s if now_s is not None else time.time())
        return max(0.0, end_s - created_s)

    def prompt_one_line(self) -> str:
        line = (self.prompt or "").strip().splitlines()[0] if self.prompt else ""
        return line or "(empty prompt)"

    def info_one_line(self) -> str:
        if self.error:
            return self.error.replace("\n", " ").strip()
        duration = self.elapsed_seconds()
        if self.exit_code is None:
            if self.is_active():
                return f"elapsed {_format_duration(duration)}"
            return ""
        if self.exit_code == 0:
            return f"ok • {_format_duration(duration)}"
        return f"exit {self.exit_code} • {_format_duration(duration)}"

    def is_active(self) -> bool:
        return (self.status or "").lower() in {"queued", "pulling", "created", "running", "starting"}

    def is_done(self) -> bool:
        return (self.status or "").lower() == "done"

    def is_failed(self) -> bool:
        return (self.status or "").lower() in {"failed", "error"}


def _task_display_status(task: Task) -> str:
    status = (task.status or "").lower()
    if status == "done":
        return "Done"
    if status in {"failed", "error"}:
        return "Failed"
    if status == "pulling":
        return "Pulling"
    if status == "running":
        return "Running"
    if status == "created":
        return "Created"
    if status == "queued":
        return "Queued"
    if status == "starting":
        return "Starting"
    if status == "paused":
        return "Paused"
    if status == "restarting":
        return "Restarting"
    if status == "removing":
        return "Removing"
    if status == "exited" and task.exit_code == 0:
        return "Done"
    if status == "exited" and task.exit_code is not None:
        return f"Exit {task.exit_code}"
    if status == "unknown":
        return "Unknown"
    return status.title() if status else "—"


class TaskRunnerBridge(QObject):
    state = Signal(dict)
    log = Signal(str)
    done = Signal(int, object)

    def __init__(self, task_id: str, config: DockerRunnerConfig, prompt: str = "", mode: str = "codex") -> None:
        super().__init__()
        self.task_id = task_id
        if mode == "preflight":
            self._worker = DockerPreflightWorker(
                config=config,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )
        else:
            self._worker = DockerCodexWorker(
                config=config,
                prompt=prompt,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )

    @property
    def container_id(self) -> str | None:
        return self._worker.container_id

    def request_stop(self) -> None:
        self._worker.request_stop()

    def run(self) -> None:
        self._worker.run()


class TaskRow(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_id: str | None = None
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._task = ElidedLabel("—")
        self._task.setStyleSheet("font-weight: 650; color: rgba(237, 239, 245, 235);")
        self._task.setMinimumWidth(260)
        self._task.setTextInteractionFlags(Qt.NoTextInteraction)
        self._task.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        state_wrap = QWidget()
        state_layout = QHBoxLayout(state_wrap)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(8)
        self._glyph = StatusGlyph(size=18)
        self._glyph.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._status = QLabel("idle")
        self._status.setStyleSheet("color: rgba(237, 239, 245, 190);")
        self._status.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        state_layout.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_layout.addWidget(self._status, 0, Qt.AlignLeft)
        state_wrap.setMinimumWidth(180)
        state_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._info = ElidedLabel("")
        self._info.setStyleSheet("color: rgba(237, 239, 245, 150);")
        self._info.setTextInteractionFlags(Qt.NoTextInteraction)
        self._info.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(self._task, 5)
        layout.addWidget(state_wrap, 0)
        layout.addWidget(self._info, 4)

        self.setCursor(Qt.PointingHandCursor)
        self.set_stain("slate")

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def set_task_id(self, task_id: str) -> None:
        self._task_id = task_id

    def set_stain(self, stain: str) -> None:
        if (self.property("stain") or "") == stain:
            return
        self.setProperty("stain", stain)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_task(self, text: str) -> None:
        self._task.setFullText(text)

    def set_info(self, text: str) -> None:
        self._info.setFullText(text)

    def update_from_task(self, task: Task, spinner_color: QColor | None = None) -> None:
        self.set_task(task.prompt_one_line())
        self.set_info(task.info_one_line())

        display = _task_display_status(task)
        status_key = (task.status or "").lower()
        color = _status_color(status_key)
        self._status.setText(display)
        self._status.setStyleSheet(f"color: {_rgba(color, 235)}; font-weight: 700;")

        if task.is_active():
            self._glyph.set_mode("spinner", spinner_color or color)
            return
        if task.is_done():
            self._glyph.set_mode("check", color)
            return
        if task.is_failed() or (task.exit_code is not None and task.exit_code != 0):
            self._glyph.set_mode("x", color)
            return
        self._glyph.set_mode("idle", color)


class DashboardPage(QWidget):
    task_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = GlassCard()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(8, 0, 8, 0)
        columns_layout.setSpacing(12)
        c1 = QLabel("Task")
        c1.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c2 = QLabel("State")
        c2.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c3 = QLabel("Info")
        c3.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c1.setMinimumWidth(260)
        c2.setMinimumWidth(180)
        columns_layout.addWidget(c1, 5)
        columns_layout.addWidget(c2, 0)
        columns_layout.addWidget(c3, 4)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("TaskScroll")

        self._list = QWidget()
        self._list.setObjectName("TaskList")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list)

        table_layout.addWidget(columns)
        table_layout.addWidget(self._scroll, 1)
        layout.addWidget(table, 1)

        self._rows: dict[str, TaskRow] = {}

    def _pick_new_row_stain(self) -> str:
        stains = ("cyan", "emerald", "violet", "rose", "amber")
        current: str | None = None
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, TaskRow):
                current = str(widget.property("stain") or "")
                break
        if current in stains:
            return stains[(stains.index(current) + 1) % len(stains)]
        return stains[0]

    def upsert_task(self, task: Task, stain: str | None = None, spinner_color: QColor | None = None) -> None:
        row = self._rows.get(task.task_id)
        if row is None:
            row = TaskRow()
            row.set_task_id(task.task_id)
            row.set_stain(stain or self._pick_new_row_stain())
            row.clicked.connect(self._on_row_clicked)
            self._rows[task.task_id] = row
            self._list_layout.insertWidget(0, row)
        elif stain:
            row.set_stain(stain)

        row.update_from_task(task, spinner_color=spinner_color)

    def _on_row_clicked(self) -> None:
        row = self.sender()
        if isinstance(row, TaskRow) and row.task_id:
            self.task_selected.emit(row.task_id)

    def remove_tasks(self, task_ids: set[str]) -> None:
        for task_id in task_ids:
            row = self._rows.pop(task_id, None)
            if row is not None:
                row.setParent(None)
                row.deleteLater()


class TaskDetailsPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        self._title = QLabel("Task")
        self._title.setStyleSheet("font-size: 18px; font-weight: 750;")
        self._subtitle = QLabel("—")
        self._subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        layout.addLayout(mid, 2)

        left = GlassCard()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        ptitle = QLabel("Prompt")
        ptitle.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._prompt = QPlainTextEdit()
        self._prompt.setReadOnly(True)
        self._prompt.setMaximumBlockCount(2000)

        cfg = QGridLayout()
        cfg.setHorizontalSpacing(10)
        cfg.setVerticalSpacing(8)

        self._workdir = QLabel("—")
        self._codexdir = QLabel("—")
        self._container = QLabel("—")
        self._container.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workdir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._codexdir.setTextInteractionFlags(Qt.TextSelectableByMouse)

        cfg.addWidget(QLabel("Host Workdir"), 0, 0)
        cfg.addWidget(self._workdir, 0, 1)
        cfg.addWidget(QLabel("Host Config folder"), 1, 0)
        cfg.addWidget(self._codexdir, 1, 1)
        cfg.addWidget(QLabel("Container ID"), 2, 0)
        cfg.addWidget(self._container, 2, 1)

        left_layout.addWidget(ptitle)
        left_layout.addWidget(self._prompt, 1)
        left_layout.addLayout(cfg)
        mid.addWidget(left, 3)

        right = GlassCard()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        stitle = QLabel("Container state")
        stitle.setStyleSheet("font-size: 14px; font-weight: 650;")

        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        self._glyph = StatusGlyph(size=44)
        self._status = QLabel("idle")
        self._status.setStyleSheet("font-size: 16px; font-weight: 750;")
        state_row.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_row.addWidget(self._status, 1)

        details = QGridLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(8)

        self._started = QLabel("—")
        self._uptime = QLabel("—")
        self._exit = QLabel("—")
        details.addWidget(QLabel("Started"), 0, 0)
        details.addWidget(self._started, 0, 1)
        details.addWidget(QLabel("Elapsed"), 1, 0)
        details.addWidget(self._uptime, 1, 1)
        details.addWidget(QLabel("Exit code"), 2, 0)
        details.addWidget(self._exit, 2, 1)

        right_layout.addWidget(stitle)
        right_layout.addLayout(state_row)
        right_layout.addLayout(details)
        right_layout.addStretch(1)
        mid.addWidget(right, 2)

        logs = GlassCard()
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(18, 16, 18, 16)
        logs_layout.setSpacing(10)

        ltitle = QLabel("Logs")
        ltitle.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._logs = QPlainTextEdit()
        self._logs.setReadOnly(True)
        self._logs.setMaximumBlockCount(5000)
        self._log_highlighter = LogHighlighter(self._logs.document())
        logs_layout.addWidget(ltitle)
        logs_layout.addWidget(self._logs, 1)
        layout.addWidget(logs, 2)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick_uptime)
        self._ticker.start()

        self._last_task: Task | None = None

    def show_task(self, task: Task) -> None:
        self._current_task_id = task.task_id
        self._last_task = task
        self._title.setText(f"Task {task.task_id}")
        self._subtitle.setText(task.prompt_one_line())
        self._prompt.setPlainText(task.prompt)
        self._workdir.setText(task.host_workdir)
        self._codexdir.setText(task.host_codex_dir)
        self._container.setText(task.container_id or "—")
        self._logs.setPlainText("\n".join(task.logs[-5000:]))
        self._apply_status(task)
        self._tick_uptime()

    def append_log(self, task_id: str, line: str) -> None:
        if self._current_task_id != task_id:
            return
        self._logs.appendPlainText(line)

    def update_task(self, task: Task) -> None:
        if self._current_task_id != task.task_id:
            return
        self._last_task = task
        self._container.setText(task.container_id or "—")
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
        self._apply_status(task)
        self._tick_uptime()

    def _apply_status(self, task: Task) -> None:
        status = _task_display_status(task)
        color = _status_color(task.status)
        self._status.setText(status)
        self._status.setStyleSheet(
            "font-size: 16px; font-weight: 750; " f"color: {_rgba(color, 235)};"
        )
        if task.is_active():
            self._glyph.set_mode("spinner", color)
        elif task.is_done():
            self._glyph.set_mode("check", color)
        elif task.is_failed() or status.startswith("Exit "):
            self._glyph.set_mode("x", color)
        else:
            self._glyph.set_mode("idle", color)

        started_local = "—"
        if task.started_at:
            started_local = task.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self._started.setText(started_local)
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))

    def _tick_uptime(self) -> None:
        task = self._last_task
        if not task:
            self._uptime.setText("—")
            return
        self._uptime.setText(_format_duration(task.elapsed_seconds()))


class NewTaskPage(QWidget):
    requested_run = Signal(str, str, str, str)
    back_requested = Signal()
    environment_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title = QLabel("New task")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        top_row.addWidget(title)
        top_row.addStretch(1)
        top_row.addWidget(back, 0, Qt.AlignRight)

        header_layout.addLayout(top_row)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        prompt_title = QLabel("Prompt")
        prompt_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._prompt = QPlainTextEdit()
        self._prompt.setPlaceholderText("Describe what you want Codex to do…")
        self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt.setTabChangesFocus(True)

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(10)

        self._environment = QComboBox()
        self._environment.currentIndexChanged.connect(self._on_environment_changed)

        self._host_codex = QLineEdit(os.path.expanduser("~/.codex"))
        self._host_workdir = QLineEdit(os.getcwd())

        self._browse_workdir = QPushButton("Browse…")
        self._browse_workdir.clicked.connect(self._pick_workdir)
        self._browse_workdir.setFixedWidth(100)

        cfg_grid.addWidget(QLabel("Environment"), 0, 0)
        cfg_grid.addWidget(self._environment, 0, 1, 1, 2)
        cfg_grid.addWidget(QLabel("Host Config folder"), 1, 0)
        cfg_grid.addWidget(self._host_codex, 1, 1, 1, 2)
        cfg_grid.addWidget(QLabel("Host Workdir"), 2, 0)
        cfg_grid.addWidget(self._host_workdir, 2, 1)
        cfg_grid.addWidget(self._browse_workdir, 2, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._run = QPushButton("Run")
        self._run.clicked.connect(self._on_run)
        buttons.addWidget(self._run)
        buttons.addStretch(1)

        card_layout.addWidget(prompt_title)
        card_layout.addWidget(self._prompt, 1)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

    def _pick_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select host Workdir", self._host_workdir.text())
        if path:
            self._host_workdir.setText(path)

    def _on_run(self) -> None:
        prompt = (self._prompt.toPlainText() or "").strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Enter a prompt first.")
            return
        prompt = sanitize_prompt(prompt)

        host_codex = os.path.expanduser((self._host_codex.text() or "").strip())
        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        env_id = str(self._environment.currentData() or "")
        self.requested_run.emit(prompt, host_workdir, host_codex, env_id)

    def _on_environment_changed(self, index: int) -> None:
        self.environment_changed.emit(str(self._environment.currentData() or ""))

    def set_environments(self, envs: list[tuple[str, str]], active_id: str) -> None:
        current = str(self._environment.currentData() or "")
        self._environment.blockSignals(True)
        try:
            self._environment.clear()
            for env_id, name in envs:
                self._environment.addItem(name, env_id)
            desired = active_id or current
            idx = self._environment.findData(desired)
            if idx >= 0:
                self._environment.setCurrentIndex(idx)
        finally:
            self._environment.blockSignals(False)

    def set_environment_id(self, env_id: str) -> None:
        idx = self._environment.findData(env_id)
        if idx >= 0:
            self._environment.setCurrentIndex(idx)

    def set_defaults(self, host_workdir: str, host_codex: str) -> None:
        if host_workdir:
            self._host_workdir.setText(host_workdir)
        if host_codex:
            self._host_codex.setText(host_codex)

    def get_defaults(self) -> tuple[str, str]:
        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())
        host_codex = os.path.expanduser((self._host_codex.text() or "").strip())
        return host_workdir, host_codex

    def reset_for_new_run(self) -> None:
        self._prompt.setPlainText("")
        self._prompt.setFocus(Qt.OtherFocusReason)


class EnvironmentsPage(QWidget):
    back_requested = Signal()
    updated = Signal(str)
    test_preflight_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._environments: dict[str, Environment] = {}
        self._current_env_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title = QLabel("Environments")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        subtitle = QLabel("Saved locally in ~/.midoriai/codex-container-gui/")
        subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._env_select = QComboBox()
        self._env_select.currentIndexChanged.connect(self._on_env_selected)

        new_btn = QToolButton()
        new_btn.setText("New")
        new_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        new_btn.clicked.connect(self._on_new)

        delete_btn = QToolButton()
        delete_btn.setText("Delete")
        delete_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        delete_btn.clicked.connect(self._on_delete)

        save_btn = QToolButton()
        save_btn.setText("Save")
        save_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save_btn.clicked.connect(self._on_save)

        test_btn = QToolButton()
        test_btn.setText("Test preflight")
        test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_btn.clicked.connect(self._on_test_preflight)

        top_row.addWidget(QLabel("Environment"))
        top_row.addWidget(self._env_select, 1)
        top_row.addWidget(new_btn)
        top_row.addWidget(delete_btn)
        top_row.addWidget(test_btn)
        top_row.addWidget(save_btn)
        card_layout.addLayout(top_row)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self._name = QLineEdit()
        self._color = QComboBox()
        for stain in ALLOWED_STAINS:
            self._color.addItem(stain.title(), stain)

        self._host_workdir = QLineEdit()
        self._host_codex_dir = QLineEdit()
        self._codex_args = QLineEdit()

        browse_workdir = QPushButton("Browse…")
        browse_workdir.setFixedWidth(100)
        browse_workdir.clicked.connect(self._pick_workdir)

        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(100)
        browse_codex.clicked.connect(self._pick_codex_dir)

        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(self._name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Color"), 1, 0)
        grid.addWidget(self._color, 1, 1, 1, 2)
        grid.addWidget(QLabel("Default Host Workdir"), 2, 0)
        grid.addWidget(self._host_workdir, 2, 1)
        grid.addWidget(browse_workdir, 2, 2)
        grid.addWidget(QLabel("Default Host Config folder"), 3, 0)
        grid.addWidget(self._host_codex_dir, 3, 1)
        grid.addWidget(browse_codex, 3, 2)
        grid.addWidget(QLabel("Codex extra args"), 4, 0)
        grid.addWidget(self._codex_args, 4, 1, 1, 2)

        general_layout.addLayout(grid)

        self._preflight_enabled = QCheckBox("Enable environment preflight bash (runs after Settings preflight)")
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before `codex exec`.\n"
            "# Runs after Settings preflight (if enabled).\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        preflight_tab = QWidget()
        preflight_layout = QVBoxLayout(preflight_tab)
        preflight_layout.setSpacing(10)
        preflight_layout.addWidget(self._preflight_enabled)
        preflight_layout.addWidget(QLabel("Preflight script"))
        preflight_layout.addWidget(self._preflight_script, 1)

        self._env_vars = QPlainTextEdit()
        self._env_vars.setPlaceholderText("# KEY=VALUE (one per line)\n")
        self._env_vars.setTabChangesFocus(True)
        env_vars_tab = QWidget()
        env_vars_layout = QVBoxLayout(env_vars_tab)
        env_vars_layout.setSpacing(10)
        env_vars_layout.addWidget(QLabel("Container env vars"))
        env_vars_layout.addWidget(self._env_vars, 1)

        self._mounts = QPlainTextEdit()
        self._mounts.setPlaceholderText("# host_path:container_path[:ro]\n")
        self._mounts.setTabChangesFocus(True)
        mounts_tab = QWidget()
        mounts_layout = QVBoxLayout(mounts_tab)
        mounts_layout.setSpacing(10)
        mounts_layout.addWidget(QLabel("Extra bind mounts"))
        mounts_layout.addWidget(self._mounts, 1)

        tabs.addTab(general_tab, "General")
        tabs.addTab(preflight_tab, "Preflight")
        tabs.addTab(env_vars_tab, "Env Vars")
        tabs.addTab(mounts_tab, "Mounts")

        card_layout.addWidget(tabs, 1)

        layout.addWidget(card, 1)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs)
        current = str(self._env_select.currentData() or "")

        self._env_select.blockSignals(True)
        try:
            self._env_select.clear()
            ordered = sorted(self._environments.values(), key=lambda e: (e.name or e.env_id).lower())
            for env in ordered:
                self._env_select.addItem(env.name or env.env_id, env.env_id)
            desired = active_id or current
            idx = self._env_select.findData(desired)
            if idx < 0 and self._env_select.count() > 0:
                idx = 0
            if idx >= 0:
                self._env_select.setCurrentIndex(idx)
        finally:
            self._env_select.blockSignals(False)

        self._load_selected()

    def _load_selected(self) -> None:
        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None
        if not env:
            self._name.setText("")
            self._host_workdir.setText("")
            self._host_codex_dir.setText("")
            self._codex_args.setText("")
            self._preflight_enabled.setChecked(False)
            self._preflight_script.setPlainText("")
            self._env_vars.setPlainText("")
            self._mounts.setPlainText("")
            return

        self._name.setText(env.name)
        idx = self._color.findData(env.color)
        if idx >= 0:
            self._color.setCurrentIndex(idx)
        self._host_workdir.setText(env.host_workdir)
        self._host_codex_dir.setText(env.host_codex_dir)
        self._codex_args.setText(env.codex_extra_args)
        self._preflight_enabled.setChecked(bool(env.preflight_enabled))
        self._preflight_script.setEnabled(bool(env.preflight_enabled))
        self._preflight_script.setPlainText(env.preflight_script or "")
        env_lines = "\n".join(f"{k}={v}" for k, v in sorted(env.env_vars.items()))
        self._env_vars.setPlainText(env_lines)
        self._mounts.setPlainText("\n".join(env.extra_mounts))

    def _on_env_selected(self, index: int) -> None:
        self._load_selected()

    def _pick_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select default host Workdir", self._host_workdir.text())
        if path:
            self._host_workdir.setText(path)

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select default host Config folder", self._host_codex_dir.text())
        if path:
            self._host_codex_dir.setText(path)

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New environment", "Name")
        if not ok:
            return
        name = (name or "").strip() or "New environment"

        base = self._environments.get(str(self._env_select.currentData() or ""))
        env_id = f"env-{uuid4().hex[:8]}"
        color = "emerald"
        if base and base.color in ALLOWED_STAINS:
            idx = ALLOWED_STAINS.index(base.color)
            color = ALLOWED_STAINS[(idx + 1) % len(ALLOWED_STAINS)]
        env = Environment(
            env_id=env_id,
            name=name,
            color=color,
            host_workdir=base.host_workdir if base else "",
            host_codex_dir=base.host_codex_dir if base else "",
            codex_extra_args=base.codex_extra_args if base else "",
            preflight_enabled=base.preflight_enabled if base else False,
            preflight_script=base.preflight_script if base else "",
            env_vars=dict(base.env_vars) if base else {},
            extra_mounts=list(base.extra_mounts) if base else [],
        )
        save_environment(env)
        self.updated.emit(env_id)

    def _on_delete(self) -> None:
        env_id = self._current_env_id
        env = self._environments.get(env_id or "")
        if not env:
            return
        confirm = QMessageBox.question(
            self,
            "Delete environment",
            f"Delete environment '{env.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        delete_environment(env.env_id)
        self.updated.emit("")

    def _on_save(self) -> None:
        env_id = self._current_env_id
        if not env_id:
            return
        name = (self._name.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter an environment name first.")
            return

        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        codex_args = (self._codex_args.text() or "").strip()
        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        env = Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir=host_workdir,
            host_codex_dir=host_codex_dir,
            codex_extra_args=codex_args,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
        )
        save_environment(env)
        self.updated.emit(env_id)

    def selected_environment_id(self) -> str:
        return str(self._env_select.currentData() or "")

    def _draft_environment_from_form(self) -> Environment | None:
        env_id = self._current_env_id
        if not env_id:
            return None

        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        codex_args = (self._codex_args.text() or "").strip()
        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return None

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        name = (self._name.text() or "").strip() or env_id
        return Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir=host_workdir,
            host_codex_dir=host_codex_dir,
            codex_extra_args=codex_args,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
        )

    def _on_test_preflight(self) -> None:
        env = self._draft_environment_from_form()
        if env is None:
            return
        self.test_preflight_requested.emit(env)


class SettingsPage(QWidget):
    back_requested = Signal()
    saved = Signal(dict)
    test_preflight_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        subtitle = QLabel("Saved locally in ~/.midoriai/codex-container-gui/state.json")
        subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self._use = QComboBox()
        self._use.addItem("Codex", "codex")
        self._use.addItem("Claude", "claude")
        self._use.addItem("GitHub Copilot", "copilot")
        model = self._use.model()
        if hasattr(model, "item"):
            try:
                model.item(1).setEnabled(False)
                model.item(2).setEnabled(False)
            except Exception:
                pass

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._preflight_enabled = QCheckBox("Enable settings preflight bash (runs on all envs, before env preflight)")
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before `codex exec`.\n"
            "# Runs on every environment, before environment preflight (if enabled).\n"
            "# This script is mounted read-only and deleted from the host after the task finishes.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        grid.addWidget(QLabel("Use"), 0, 0)
        grid.addWidget(self._use, 0, 1)
        grid.addWidget(QLabel("Shell"), 1, 0)
        grid.addWidget(self._shell, 1, 1)
        grid.addWidget(self._preflight_enabled, 2, 0, 1, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save = QToolButton()
        save.setText("Save")
        save.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save.clicked.connect(self._on_save)
        test = QToolButton()
        test.setText("Test preflights (all envs)")
        test.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test.clicked.connect(self._on_test_preflight)
        buttons.addWidget(test)
        buttons.addWidget(save)
        buttons.addStretch(1)

        card_layout.addLayout(grid)
        card_layout.addWidget(QLabel("Preflight script"))
        card_layout.addWidget(self._preflight_script, 1)
        card_layout.addLayout(buttons)
        layout.addWidget(card, 1)

    def set_settings(self, settings: dict) -> None:
        use_value = str(settings.get("use") or "codex").strip().lower()
        if use_value != "codex":
            use_value = "codex"
        self._set_combo_value(self._use, use_value, fallback="codex")

        shell_value = str(settings.get("shell") or "bash").strip().lower()
        self._set_combo_value(self._shell, shell_value, fallback="bash")

        enabled = bool(settings.get("preflight_enabled") or False)
        self._preflight_enabled.setChecked(enabled)
        self._preflight_script.setEnabled(enabled)
        self._preflight_script.setPlainText(str(settings.get("preflight_script") or ""))

    def get_settings(self) -> dict:
        return {
            "use": str(self._use.currentData() or "codex"),
            "shell": str(self._shell.currentData() or "bash"),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
        }

    def _on_save(self) -> None:
        self.saved.emit(self.get_settings())

    def _on_test_preflight(self) -> None:
        self.test_preflight_requested.emit(self.get_settings())

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(1280, 720)

        self._settings_data: dict[str, object] = {
            "use": "codex",
            "shell": "bash",
            "preflight_enabled": False,
            "preflight_script": "",
            "host_workdir": os.environ.get("CODEX_HOST_WORKDIR", os.getcwd()),
            "host_codex_dir": os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")),
            "active_environment_id": "default",
        }
        self._environments: dict[str, Environment] = {}
        self._syncing_environment = False
        self._tasks: dict[str, Task] = {}
        self._threads: dict[str, QThread] = {}
        self._bridges: dict[str, TaskRunnerBridge] = {}
        self._run_started_s: dict[str, float] = {}
        self._state_path = default_state_path()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_state)

        self._dashboard_ticker = QTimer(self)
        self._dashboard_ticker.setInterval(1000)
        self._dashboard_ticker.timeout.connect(self._tick_dashboard_elapsed)
        self._dashboard_ticker.start()

        root = GlassRoot()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        top = GlassCard()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 12, 14, 12)
        top_layout.setSpacing(10)

        self._btn_new = QToolButton()
        self._btn_new.setText("New task")
        self._btn_new.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self._btn_new.clicked.connect(self._show_new_task)

        self._btn_new_interactive = QToolButton()
        self._btn_new_interactive.setText("New task (interactive)")
        self._btn_new_interactive.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new_interactive.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        self._btn_clean = QToolButton()
        self._btn_clean.setText("Clean old tasks")
        self._btn_clean.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_clean.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_clean.clicked.connect(self._clean_old_tasks)

        self._btn_envs = QToolButton()
        self._btn_envs.setText("Environments")
        self._btn_envs.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_envs.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self._btn_envs.clicked.connect(self._show_environments)

        self._btn_settings = QToolButton()
        self._btn_settings.setText("Settings")
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self._btn_settings.clicked.connect(self._show_settings)

        self._env_picker_label = QLabel("Environment")
        self._env_picker_label.setStyleSheet("color: rgba(237, 239, 245, 170); font-weight: 650;")
        self._env_picker = QComboBox()
        self._env_picker.setFixedWidth(260)
        self._env_picker.currentIndexChanged.connect(self._on_env_picker_changed)

        top_layout.addWidget(self._btn_new)
        top_layout.addWidget(self._btn_new_interactive)
        top_layout.addWidget(self._btn_clean)
        top_layout.addWidget(self._btn_envs)
        top_layout.addWidget(self._btn_settings)
        top_layout.addStretch(1)
        top_layout.addWidget(self._env_picker_label, 0, Qt.AlignRight)
        top_layout.addWidget(self._env_picker, 0, Qt.AlignRight)

        outer.addWidget(top)

        self._dashboard = DashboardPage()
        self._dashboard.task_selected.connect(self._open_task_details)
        self._new_task = NewTaskPage()
        self._new_task.requested_run.connect(self._start_task_from_ui)
        self._new_task.environment_changed.connect(self._on_new_task_env_changed)
        self._new_task.back_requested.connect(self._show_dashboard)
        self._details = TaskDetailsPage()
        self._details.back_requested.connect(self._show_dashboard)
        self._envs_page = EnvironmentsPage()
        self._envs_page.back_requested.connect(self._show_dashboard)
        self._envs_page.updated.connect(self._reload_environments, Qt.QueuedConnection)
        self._envs_page.test_preflight_requested.connect(self._on_environment_test_preflight, Qt.QueuedConnection)
        self._settings = SettingsPage()
        self._settings.back_requested.connect(self._show_dashboard)
        self._settings.saved.connect(self._apply_settings, Qt.QueuedConnection)
        self._settings.test_preflight_requested.connect(self._on_settings_test_preflight, Qt.QueuedConnection)

        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        self._stack_layout.setSpacing(0)
        self._stack_layout.addWidget(self._dashboard)
        self._stack_layout.addWidget(self._new_task)
        self._stack_layout.addWidget(self._details)
        self._stack_layout.addWidget(self._envs_page)
        self._stack_layout.addWidget(self._settings)
        self._dashboard.show()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        outer.addWidget(self._stack, 1)

        self._load_state()
        self._reload_environments()
        self._apply_settings_to_pages()

    def _show_dashboard(self) -> None:
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._dashboard.show()

    def _show_new_task(self) -> None:
        self._dashboard.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._new_task.reset_for_new_run()
        self._new_task.show()

    def _show_task_details(self) -> None:
        self._dashboard.hide()
        self._new_task.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._details.show()

    def _show_environments(self) -> None:
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._settings.hide()
        self._envs_page.set_environments(self._environments, self._active_environment_id())
        self._envs_page.show()

    def _show_settings(self) -> None:
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.set_settings(self._settings_data)
        self._settings.show()

    def _apply_settings_to_pages(self) -> None:
        self._settings.set_settings(self._settings_data)
        self._apply_active_environment_to_new_task()

    def _apply_settings(self, settings: dict) -> None:
        merged = dict(self._settings_data)
        merged.update(settings or {})
        use_value = str(merged.get("use") or "codex").lower()
        if use_value != "codex":
            use_value = "codex"
        merged["use"] = use_value

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        self._settings_data = merged
        self._apply_settings_to_pages()
        self._schedule_save()

    def _active_environment_id(self) -> str:
        return str(self._settings_data.get("active_environment_id") or "default")

    def _environment_list(self) -> list[Environment]:
        return sorted(self._environments.values(), key=lambda e: (e.name or e.env_id).lower())

    def _populate_environment_pickers(self) -> None:
        active_id = self._active_environment_id()
        envs = self._environment_list()

        self._syncing_environment = True
        try:
            self._env_picker.blockSignals(True)
            try:
                self._env_picker.clear()
                for env in envs:
                    self._env_picker.addItem(env.name or env.env_id, env.env_id)
                idx = self._env_picker.findData(active_id)
                if idx >= 0:
                    self._env_picker.setCurrentIndex(idx)
            finally:
                self._env_picker.blockSignals(False)

            self._new_task.set_environments([(e.env_id, e.name or e.env_id) for e in envs], active_id=active_id)
            self._new_task.set_environment_id(active_id)
        finally:
            self._syncing_environment = False

    def _apply_active_environment_to_new_task(self) -> None:
        env = self._environments.get(self._active_environment_id())
        host_workdir = str(self._settings_data.get("host_workdir") or os.getcwd())
        host_codex = str(self._settings_data.get("host_codex_dir") or os.path.expanduser("~/.codex"))
        if env:
            if env.host_workdir:
                host_workdir = env.host_workdir
            if env.host_codex_dir:
                host_codex = env.host_codex_dir
        self._new_task.set_defaults(host_workdir=host_workdir, host_codex=host_codex)
        self._populate_environment_pickers()

    def _on_env_picker_changed(self, index: int) -> None:
        if self._syncing_environment:
            return
        env_id = str(self._env_picker.currentData() or "")
        if env_id and env_id in self._environments:
            self._settings_data["active_environment_id"] = env_id
            self._apply_active_environment_to_new_task()
            self._schedule_save()

    def _on_new_task_env_changed(self, env_id: str) -> None:
        if self._syncing_environment:
            return
        env_id = str(env_id or "")
        if env_id and env_id in self._environments:
            self._settings_data["active_environment_id"] = env_id
            self._apply_active_environment_to_new_task()
            self._schedule_save()

    def _refresh_task_rows(self) -> None:
        for task in self._tasks.values():
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _tick_dashboard_elapsed(self) -> None:
        if not self._dashboard.isVisible():
            return
        for task in self._tasks.values():
            if not task.is_active():
                continue
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _reload_environments(self, preferred_env_id: str = "") -> None:
        envs = load_environments()
        if not envs:
            active_workdir = str(self._settings_data.get("host_workdir") or os.getcwd())
            active_codex = str(self._settings_data.get("host_codex_dir") or os.path.expanduser("~/.codex"))
            env = Environment(
                env_id="default",
                name="Default",
                color="emerald",
                host_workdir=active_workdir,
                host_codex_dir=active_codex,
                preflight_enabled=False,
                preflight_script="",
            )
            save_environment(env)
            envs = load_environments()

        self._environments = dict(envs)
        active_id = self._active_environment_id()
        if active_id not in self._environments:
            if "default" in self._environments:
                self._settings_data["active_environment_id"] = "default"
            else:
                ordered = self._environment_list()
                if ordered:
                    self._settings_data["active_environment_id"] = ordered[0].env_id
        for task in self._tasks.values():
            if not task.environment_id:
                task.environment_id = self._active_environment_id()
        if self._envs_page.isVisible():
            selected = preferred_env_id or self._envs_page.selected_environment_id() or self._active_environment_id()
            self._envs_page.set_environments(self._environments, selected)
        self._apply_active_environment_to_new_task()
        self._refresh_task_rows()

    def _clean_old_tasks(self) -> None:
        to_remove: set[str] = set()
        for task_id, task in self._tasks.items():
            status = (task.status or "").lower()
            if status in {"done", "failed", "error"} and not task.is_active():
                to_remove.add(task_id)
        if not to_remove:
            return
        self._dashboard.remove_tasks(to_remove)
        for task_id in to_remove:
            self._tasks.pop(task_id, None)
            self._threads.pop(task_id, None)
            self._bridges.pop(task_id, None)
            self._run_started_s.pop(task_id, None)
        self._schedule_save()

    def _start_task_from_ui(self, prompt: str, host_workdir: str, host_codex: str, env_id: str) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return
        prompt = sanitize_prompt((prompt or "").strip())

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        self._settings_data["host_workdir"] = host_workdir
        self._settings_data["host_codex_dir"] = host_codex

        task_id = uuid4().hex[:10]
        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        self._settings_data["active_environment_id"] = env_id
        env = self._environments.get(env_id)

        image = PIXELARCH_EMERALD_IMAGE

        codex_extra_args: list[str] = []
        if env and env.codex_extra_args.strip():
            try:
                codex_extra_args = shlex.split(env.codex_extra_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Codex args", str(exc))
                return

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="pulling",
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_codex,
            host_workdir=host_workdir,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            codex_extra_args=codex_extra_args,
        )
        bridge = TaskRunnerBridge(task_id=task_id, config=config, prompt=prompt)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task_id] = bridge
        self._threads[task_id] = thread
        self._run_started_s[task_id] = time.time()

        thread.start()
        self._show_dashboard()
        self._new_task.reset_for_new_run()
        self._schedule_save()

    def _start_preflight_task(
        self,
        *,
        label: str,
        env: Environment,
        host_workdir: str,
        host_codex: str,
        settings_preflight_script: str | None,
        environment_preflight_script: str | None,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if not (settings_preflight_script or "").strip() and not (environment_preflight_script or "").strip():
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

        task_id = uuid4().hex[:10]
        image = PIXELARCH_EMERALD_IMAGE

        task = Task(
            task_id=task_id,
            prompt=label,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env.env_id,
            created_at_s=time.time(),
            status="pulling",
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_codex,
            host_workdir=host_workdir,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            codex_extra_args=[],
        )
        bridge = TaskRunnerBridge(task_id=task_id, config=config, mode="preflight")
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task_id] = bridge
        self._threads[task_id] = thread
        self._run_started_s[task_id] = time.time()

        thread.start()
        self._show_dashboard()
        self._schedule_save()

    def _on_settings_test_preflight(self, settings: dict) -> None:
        settings_script: str | None = None
        if bool(settings.get("preflight_enabled") or False):
            candidate = str(settings.get("preflight_script") or "")
            if candidate.strip():
                settings_script = candidate

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        host_codex_base = str(self._settings_data.get("host_codex_dir") or os.path.expanduser("~/.codex"))

        if settings_script is None:
            has_env_preflights = any(
                e.preflight_enabled and (e.preflight_script or "").strip() for e in self._environment_list()
            )
            if not has_env_preflights:
                QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
                return

        skipped: list[str] = []
        for env in self._environment_list():
            host_workdir = env.host_workdir or host_workdir_base
            host_codex = env.host_codex_dir or host_codex_base
            if not os.path.isdir(host_workdir):
                skipped.append(f"{env.name or env.env_id} ({host_workdir})")
                continue
            env_script: str | None = None
            if env.preflight_enabled and (env.preflight_script or "").strip():
                env_script = env.preflight_script
            self._start_preflight_task(
                label=f"Preflight test (all): {env.name or env.env_id}",
                env=env,
                host_workdir=host_workdir,
                host_codex=host_codex,
                settings_preflight_script=settings_script,
                environment_preflight_script=env_script,
            )

        if skipped:
            QMessageBox.warning(
                self,
                "Skipped environments",
                "Skipped environments with missing Workdir:\n" + "\n".join(skipped[:20]),
            )

    def _on_environment_test_preflight(self, env: object) -> None:
        if not isinstance(env, Environment):
            return

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        host_codex_base = str(self._settings_data.get("host_codex_dir") or os.path.expanduser("~/.codex"))
        host_workdir = env.host_workdir or host_workdir_base
        host_codex = env.host_codex_dir or host_codex_base

        self._start_preflight_task(
            label=f"Preflight test: {env.name or env.env_id}",
            env=env,
            host_workdir=host_workdir,
            host_codex=host_codex,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
        )

    def _open_task_details(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        self._details.show_task(task)
        self._show_task_details()

    def _on_bridge_state(self, state: dict) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_state(bridge.task_id, state)

    def _on_bridge_log(self, line: str) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_log(bridge.task_id, line)

    def _on_bridge_done(self, exit_code: int, error: object) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_done(bridge.task_id, exit_code, error)

    def _on_task_log(self, task_id: str, line: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        cleaned = prettify_log_line(line)
        task.logs.append(cleaned)
        if len(task.logs) > 6000:
            task.logs = task.logs[-5000:]
        self._details.append_log(task_id, cleaned)
        self._schedule_save()
        if "docker pull" in cleaned and (task.status or "").lower() != "pulling":
            task.status = "pulling"
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

    def _on_task_state(self, task_id: str, state: dict) -> None:
        task = self._tasks.get(task_id)
        bridge = self._bridges.get(task_id)
        if task is None:
            return

        current = (task.status or "").lower()
        incoming = str(state.get("Status") or task.status or "—").lower()
        if current not in {"done", "failed"}:
            task.status = incoming
        if bridge and bridge.container_id:
            task.container_id = bridge.container_id

        started_at = _parse_docker_time(state.get("StartedAt"))
        finished_at = _parse_docker_time(state.get("FinishedAt"))
        if started_at:
            task.started_at = started_at
        if finished_at:
            task.finished_at = finished_at

        exit_code = state.get("ExitCode")
        if exit_code is not None:
            try:
                task.exit_code = int(exit_code)
            except Exception:
                pass

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _on_task_done(self, task_id: str, exit_code: int, error: object) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        if task.started_at is None:
            started_s = self._run_started_s.get(task_id)
            if started_s is not None:
                task.started_at = datetime.fromtimestamp(started_s, tz=timezone.utc)
        if task.finished_at is None:
            task.finished_at = datetime.now(tz=timezone.utc)

        if error:
            task.status = "failed"
            task.error = str(error)
        else:
            task.exit_code = int(exit_code)
            task.status = "done" if int(exit_code) == 0 else "failed"

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def closeEvent(self, event) -> None:
        try:
            self._save_state()
        except Exception:
            pass
        super().closeEvent(event)

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _save_state(self) -> None:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at_s)
        payload = {"tasks": [serialize_task(t) for t in tasks], "settings": dict(self._settings_data)}
        save_state(self._state_path, payload)

    def _load_state(self) -> None:
        try:
            payload = load_state(self._state_path)
        except Exception:
            return
        settings = payload.get("settings")
        if isinstance(settings, dict):
            self._settings_data.update(settings)
        host_codex_dir = os.path.normpath(os.path.expanduser(str(self._settings_data.get("host_codex_dir") or "").strip()))
        if host_codex_dir == os.path.expanduser("~/.midoriai"):
            self._settings_data["host_codex_dir"] = os.path.expanduser("~/.codex")
        items = payload.get("tasks") or []
        loaded: list[Task] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            task = deserialize_task(Task, item)
            if not task.task_id:
                continue
            if task.logs:
                task.logs = [prettify_log_line(line) for line in task.logs if isinstance(line, str)]
            loaded.append(task)
        loaded.sort(key=lambda t: t.created_at_s)
        for task in loaded:
            active = (task.status or "").lower() in {"queued", "pulling", "created", "running", "starting"}
            if active:
                task.status = "unknown"
            self._tasks[task.task_id] = task
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)


def run_app(argv: list[str]) -> None:
    app = QApplication(argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = _app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
