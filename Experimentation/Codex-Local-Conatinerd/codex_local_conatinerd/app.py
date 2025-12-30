import os
import sys
import time
import random
import math
import shutil
import shlex
import tempfile
import subprocess
import threading

from pathlib import Path
from uuid import uuid4
from datetime import datetime
from datetime import timezone
from dataclasses import dataclass
from dataclasses import field

from PySide6.QtCore import QObject
from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtCore import QMetaObject
from PySide6.QtCore import QThread
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QIcon
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QRadialGradient
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
from codex_local_conatinerd.agent_cli import additional_config_mounts
from codex_local_conatinerd.agent_cli import container_config_dir
from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.agent_cli import verify_cli_clause
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
from codex_local_conatinerd.terminal_apps import detect_terminal_options
from codex_local_conatinerd.terminal_apps import launch_in_terminal
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


def _blend_rgb(a: QColor, b: QColor, t: float) -> QColor:
    t = float(min(max(t, 0.0), 1.0))
    r = int(round(a.red() + (b.red() - a.red()) * t))
    g = int(round(a.green() + (b.green() - a.green()) * t))
    bb = int(round(a.blue() + (b.blue() - a.blue()) * t))
    return QColor(r, g, bb)


def _apply_environment_combo_tint(combo: QComboBox, stain: str) -> None:
    env = _stain_color(stain)
    base = QColor(18, 20, 28)
    tinted = _blend_rgb(base, QColor(env.red(), env.green(), env.blue()), 0.40)
    combo.setStyleSheet(
        "\n".join(
            [
                "QComboBox {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 190))};",
                "}",
                "QComboBox::drop-down {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 135))};",
                "}",
                "QComboBox QAbstractItemView {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 240))};",
                f"  selection-background-color: {_rgba(QColor(env.red(), env.green(), env.blue(), 95))};",
                "}",
            ]
        )
    )


class _EnvironmentTintOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None, alpha: int = 13) -> None:
        super().__init__(parent)
        self._alpha = int(min(max(alpha, 0), 255))
        self._color = QColor(0, 0, 0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def set_tint_color(self, color: QColor | None) -> None:
        if color is None:
            self._color = QColor(0, 0, 0, 0)
        else:
            self._color = QColor(color.red(), color.green(), color.blue(), self._alpha)
        self.update()

    def paintEvent(self, event) -> None:
        if self._color.alpha() <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


@dataclass
class _BackgroundOrb:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: QColor

    def render_radius(self) -> float:
        return self.radius * 1.65


class GlassRoot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animate_orbs = False
        self._orb_rng = random.Random()
        self._orbs: list[_BackgroundOrb] = []
        self._orb_last_tick_s = time.monotonic()
        self._orb_timer: QTimer | None = None
        if self._animate_orbs:
            timer = QTimer(self)
            timer.setInterval(33)
            timer.timeout.connect(self._tick_orbs)
            timer.start()
            self._orb_timer = timer

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._constrain_orbs()

    def _theme_colors(self) -> list[QColor]:
        return [
            QColor(56, 189, 248),
            QColor(16, 185, 129),
            QColor(139, 92, 246),
            QColor(244, 63, 94),
            QColor(245, 158, 11),
        ]

    def _ensure_orbs(self) -> None:
        if self._orbs:
            return
        w = self.width()
        h = self.height()
        if w < 80 or h < 80:
            return

        colors = self._theme_colors()
        count = 9
        orbs: list[_BackgroundOrb] = []
        for idx in range(count):
            radius = self._orb_rng.uniform(140.0, 260.0)
            render_r = radius * 1.65
            x_min = render_r
            y_min = render_r
            x_max = max(x_min, w - render_r)
            y_max = max(y_min, h - render_r)

            x = self._orb_rng.uniform(x_min, x_max)
            y = self._orb_rng.uniform(y_min, y_max)

            angle = self._orb_rng.uniform(0.0, 6.283185307179586)
            speed = self._orb_rng.uniform(8.0, 22.0)
            vx = math.cos(angle) * speed if self._animate_orbs else 0.0
            vy = math.sin(angle) * speed if self._animate_orbs else 0.0

            color = colors[idx % len(colors)]
            orbs.append(_BackgroundOrb(x=x, y=y, vx=vx, vy=vy, radius=radius, color=color))

        self._orbs = orbs
        self._constrain_orbs()

    def _constrain_orbs(self) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0 or not self._orbs:
            return
        for orb in self._orbs:
            r = orb.render_radius()
            orb.x = min(max(orb.x, r), w - r)
            orb.y = min(max(orb.y, r), h - r)

    def _tick_orbs(self) -> None:
        if not self._animate_orbs:
            return
        now_s = time.monotonic()
        dt = now_s - self._orb_last_tick_s
        self._orb_last_tick_s = now_s

        if dt <= 0:
            return
        dt = min(dt, 0.060)

        self._ensure_orbs()
        if not self._orbs:
            return

        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        for orb in self._orbs:
            orb.x += orb.vx * dt
            orb.y += orb.vy * dt

            r = orb.render_radius()
            if orb.x - r <= 0.0:
                orb.x = r
                orb.vx = abs(orb.vx)
            elif orb.x + r >= w:
                orb.x = w - r
                orb.vx = -abs(orb.vx)

            if orb.y - r <= 0.0:
                orb.y = r
                orb.vy = abs(orb.vy)
            elif orb.y + r >= h:
                orb.y = h - r
                orb.vy = -abs(orb.vy)

        self.update()

    def _paint_orbs(self, painter: QPainter) -> None:
        if not self._orbs:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        for orb in self._orbs:
            for shrink, alpha in ((1.0, 34), (0.82, 24), (0.66, 16)):
                r = max(1.0, orb.render_radius() * shrink)
                center = QPointF(float(orb.x), float(orb.y))
                grad = QRadialGradient(center, float(r))
                c = orb.color
                grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
                grad.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), int(alpha * 0.30)))
                grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                painter.setBrush(grad)
                painter.drawEllipse(center, float(r), float(r))

        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(10, 12, 18))

        self._ensure_orbs()
        self._paint_orbs(painter)

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

    def last_nonblank_log_line(self) -> str:
        for line in reversed(self.logs):
            text = str(line or "").strip()
            if text:
                return text
        return ""

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
                last_line = self.last_nonblank_log_line()
                if last_line:
                    return last_line
                return f"elapsed {_format_duration(duration)}"
            return ""
        if self.exit_code == 0:
            last_line = self.last_nonblank_log_line()
            dur = _format_duration(duration)
            if last_line and dur != "—":
                return f"{last_line} • {dur}"
            if last_line:
                return last_line
            return f"ok • {dur}"
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

    @Slot()
    def request_stop(self) -> None:
        self._worker.request_stop()

    def run(self) -> None:
        self._worker.run()


class TaskRow(QWidget):
    clicked = Signal()
    discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_id: str | None = None
        self._last_task: Task | None = None
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)

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

        self._btn_discard = QToolButton()
        self._btn_discard.setObjectName("RowTrash")
        self._btn_discard.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_discard.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_discard.setToolTip("Discard task")
        self._btn_discard.setCursor(Qt.PointingHandCursor)
        self._btn_discard.setIconSize(self._btn_discard.iconSize().expandedTo(self._glyph.size()))
        self._btn_discard.clicked.connect(self._on_discard_clicked)

        layout.addWidget(self._task, 5)
        layout.addWidget(state_wrap, 0)
        layout.addWidget(self._info, 4)
        layout.addWidget(self._btn_discard, 0, Qt.AlignRight)

        self.setCursor(Qt.PointingHandCursor)
        self.set_stain("slate")

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def set_task_id(self, task_id: str) -> None:
        self._task_id = task_id

    def _on_discard_clicked(self) -> None:
        if self._task_id:
            self.discard_requested.emit(self._task_id)

    def set_stain(self, stain: str) -> None:
        if (self.property("stain") or "") == stain:
            return
        self.setProperty("stain", stain)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if bool(self.property("selected")) == selected:
            return
        self.setProperty("selected", selected)
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
        self._last_task = task
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

    def last_task(self) -> Task | None:
        return self._last_task


class DashboardPage(QWidget):
    task_selected = Signal(str)
    clean_old_requested = Signal()
    task_discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_task_id: str | None = None
        self._filter_text_tokens: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = GlassCard()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)

        filters = QWidget()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(8, 0, 8, 0)
        filters_layout.setSpacing(10)

        self._filter_text = QLineEdit()
        self._filter_text.setPlaceholderText("Filter tasks…")
        self._filter_text.textChanged.connect(self._on_filter_changed)

        self._filter_environment = QComboBox()
        self._filter_environment.setFixedWidth(240)
        self._filter_environment.addItem("All environments", "")
        self._filter_environment.currentIndexChanged.connect(self._on_filter_changed)

        self._filter_state = QComboBox()
        self._filter_state.setFixedWidth(160)
        self._filter_state.addItem("Any state", "any")
        self._filter_state.addItem("Active", "active")
        self._filter_state.addItem("Done", "done")
        self._filter_state.addItem("Failed", "failed")
        self._filter_state.currentIndexChanged.connect(self._on_filter_changed)

        clear_filters = QToolButton()
        clear_filters.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        clear_filters.setToolButtonStyle(Qt.ToolButtonIconOnly)
        clear_filters.setToolTip("Clear filters")
        clear_filters.setAccessibleName("Clear filters")
        clear_filters.clicked.connect(self._clear_filters)

        self._btn_clean_old = QToolButton()
        self._btn_clean_old.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_clean_old.setToolTip("Clean finished tasks")
        self._btn_clean_old.setAccessibleName("Clean finished tasks")
        self._btn_clean_old.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_clean_old.clicked.connect(self.clean_old_requested.emit)

        filters_layout.addWidget(self._filter_text, 1)
        filters_layout.addWidget(self._filter_environment)
        filters_layout.addWidget(self._filter_state)
        filters_layout.addWidget(clear_filters, 0, Qt.AlignRight)
        filters_layout.addWidget(self._btn_clean_old, 0, Qt.AlignRight)

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
        columns_layout.addSpacing(self._btn_clean_old.sizeHint().width())

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

        table_layout.addWidget(filters)
        table_layout.addWidget(columns)
        table_layout.addWidget(self._scroll, 1)
        layout.addWidget(table, 1)

        self._rows: dict[str, TaskRow] = {}

    def _set_selected_task_id(self, task_id: str | None) -> None:
        task_id = str(task_id or "").strip() or None
        if self._selected_task_id == task_id:
            return
        prev = self._selected_task_id
        self._selected_task_id = task_id

        if prev and prev in self._rows:
            self._rows[prev].set_selected(False)
        if task_id and task_id in self._rows:
            self._rows[task_id].set_selected(True)

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
            row.discard_requested.connect(self.task_discard_requested.emit)
            self._rows[task.task_id] = row
            self._list_layout.insertWidget(0, row)
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task, spinner_color=spinner_color)
        row.setVisible(self._row_visible_for_task(task))

    def set_environment_filter_options(self, envs: list[tuple[str, str]]) -> None:
        current = str(self._filter_environment.currentData() or "")
        self._filter_environment.blockSignals(True)
        try:
            self._filter_environment.clear()
            self._filter_environment.addItem("All environments", "")
            for env_id, label in envs:
                self._filter_environment.addItem(label or env_id, env_id)
            idx = self._filter_environment.findData(current)
            if idx < 0:
                idx = 0
            self._filter_environment.setCurrentIndex(idx)
        finally:
            self._filter_environment.blockSignals(False)
        self._apply_filters()

    def _clear_filters(self) -> None:
        self._filter_text.setText("")
        self._filter_environment.setCurrentIndex(0)
        self._filter_state.setCurrentIndex(0)

    def _on_filter_changed(self, _value: object = None) -> None:
        raw = (self._filter_text.text() or "").strip().lower()
        self._filter_text_tokens = [t for t in raw.split() if t]
        self._apply_filters()

    def _task_matches_text(self, task: Task) -> bool:
        if not self._filter_text_tokens:
            return True
        haystack = " ".join(
            [
                str(task.task_id or ""),
                str(task.environment_id or ""),
                str(task.status or ""),
                task.prompt_one_line(),
                task.info_one_line(),
            ]
        ).lower()
        return all(token in haystack for token in self._filter_text_tokens)

    @staticmethod
    def _task_matches_state(task: Task, state: str) -> bool:
        state = str(state or "any")
        if state == "any":
            return True
        if state == "active":
            return task.is_active()
        status = (task.status or "").lower()
        if state == "done":
            return task.is_done() or (status == "exited" and task.exit_code == 0)
        if state == "failed":
            if task.is_failed():
                return True
            return task.exit_code is not None and task.exit_code != 0
        return True

    def _row_visible_for_task(self, task: Task) -> bool:
        env_filter = str(self._filter_environment.currentData() or "")
        if env_filter and str(task.environment_id or "") != env_filter:
            return False
        state_filter = str(self._filter_state.currentData() or "any")
        if not self._task_matches_state(task, state_filter):
            return False
        return self._task_matches_text(task)

    def _apply_filters(self) -> None:
        for row in self._rows.values():
            task = row.last_task()
            row.setVisible(True if task is None else self._row_visible_for_task(task))

    def _on_row_clicked(self) -> None:
        row = self.sender()
        if isinstance(row, TaskRow) and row.task_id:
            self._set_selected_task_id(row.task_id)
            self.task_selected.emit(row.task_id)

    def remove_tasks(self, task_ids: set[str]) -> None:
        for task_id in task_ids:
            row = self._rows.pop(task_id, None)
            if row is not None:
                row.setParent(None)
                row.deleteLater()
            if self._selected_task_id == task_id:
                self._selected_task_id = None


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
        self._logs.setObjectName("LogsView")
        self._logs.setReadOnly(True)
        self._logs.setLineWrapMode(QPlainTextEdit.NoWrap)
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

    def current_task_id(self) -> str | None:
        return self._current_task_id

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
    requested_launch = Signal(str, str, str, str, str, str)
    back_requested = Signal()
    environment_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._env_stains: dict[str, str] = {}
        self._host_codex_dir = os.path.expanduser("~/.codex")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._environment = QComboBox()
        self._environment.currentIndexChanged.connect(self._on_environment_changed)

        header = GlassCard()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title = QLabel("New task")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")

        env_label = QLabel("Environment")
        env_label.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        top_row.addWidget(title)
        top_row.addWidget(env_label)
        top_row.addWidget(self._environment)
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
        self._prompt.setPlaceholderText("Describe what you want the agent to do…")
        self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt.setTabChangesFocus(True)

        interactive_hint = QLabel("Interactive: opens a terminal and runs the container with TTY/stdin for agent TUIs.")
        interactive_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._terminal = QComboBox()
        self._refresh_terminals()

        refresh_terminals = QToolButton()
        refresh_terminals.setText("Refresh")
        refresh_terminals.setToolButtonStyle(Qt.ToolButtonTextOnly)
        refresh_terminals.clicked.connect(self._refresh_terminals)

        self._command = QLineEdit("--sandbox danger-full-access")
        self._command.setPlaceholderText(
            "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir …), or a full container command (e.g. bash)"
        )

        interactive_grid = QGridLayout()
        interactive_grid.setHorizontalSpacing(10)
        interactive_grid.setVerticalSpacing(10)
        interactive_grid.setColumnStretch(4, 1)
        interactive_grid.addWidget(QLabel("Terminal"), 0, 0)
        interactive_grid.addWidget(self._terminal, 0, 1)
        interactive_grid.addWidget(refresh_terminals, 0, 2)
        interactive_grid.addWidget(QLabel("Container command args"), 0, 3)
        interactive_grid.addWidget(self._command, 0, 4)

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(10)
        self._host_workdir = QLineEdit(os.getcwd())

        self._browse_workdir = QPushButton("Browse…")
        self._browse_workdir.clicked.connect(self._pick_workdir)
        self._browse_workdir.setFixedWidth(100)

        cfg_grid.addWidget(QLabel("Host Workdir"), 0, 0)
        cfg_grid.addWidget(self._host_workdir, 0, 1)
        cfg_grid.addWidget(self._browse_workdir, 0, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        self._run_interactive = QPushButton("Run Interactive")
        self._run_interactive.clicked.connect(self._on_launch)
        self._run_agent = QPushButton("Run Agent")
        self._run_agent.clicked.connect(self._on_run)
        buttons.addWidget(self._run_interactive)
        buttons.addWidget(self._run_agent)

        card_layout.addWidget(prompt_title)
        card_layout.addWidget(self._prompt, 1)
        card_layout.addWidget(interactive_hint)
        card_layout.addLayout(interactive_grid)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _pick_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select host Workdir", self._host_workdir.text())
        if path:
            self._host_workdir.setText(path)

    def _refresh_terminals(self) -> None:
        current = str(self._terminal.currentData() or "")
        options = detect_terminal_options()
        self._terminal.blockSignals(True)
        try:
            self._terminal.clear()
            for opt in options:
                self._terminal.addItem(opt.label, opt.terminal_id)
            desired = current
            if desired:
                idx = self._terminal.findData(desired)
                if idx >= 0:
                    self._terminal.setCurrentIndex(idx)
                    return
            if self._terminal.count() > 0:
                self._terminal.setCurrentIndex(0)
        finally:
            self._terminal.blockSignals(False)

    def _on_run(self) -> None:
        prompt = (self._prompt.toPlainText() or "").strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Enter a prompt first.")
            return
        prompt = sanitize_prompt(prompt)

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())
        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        env_id = str(self._environment.currentData() or "")
        self.requested_run.emit(prompt, host_workdir, host_codex, env_id)

    def _on_launch(self) -> None:
        prompt = sanitize_prompt((self._prompt.toPlainText() or "").strip())
        command = (self._command.text() or "").strip()
        if not command:
            command = "bash"

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())
        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        terminal_id = str(self._terminal.currentData() or "").strip()
        if not terminal_id:
            QMessageBox.warning(
                self,
                "No terminals found",
                "Could not detect an installed terminal emulator to launch.",
            )
            return

        env_id = str(self._environment.currentData() or "")
        self.requested_launch.emit(prompt, command, host_workdir, host_codex, env_id, terminal_id)

    def _on_environment_changed(self, index: int) -> None:
        self._apply_environment_tints()
        self.environment_changed.emit(str(self._environment.currentData() or ""))

    def _apply_environment_tints(self) -> None:
        env_id = str(self._environment.currentData() or "")
        stain = (self._env_stains.get(env_id) or "").strip().lower() if env_id else ""
        if not stain:
            self._environment.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            return

        _apply_environment_combo_tint(self._environment, stain)
        self._tint_overlay.set_tint_color(_stain_color(stain))

    def set_environment_stains(self, stains: dict[str, str]) -> None:
        self._env_stains = {str(k): str(v) for k, v in (stains or {}).items()}
        self._apply_environment_tints()

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
        self._apply_environment_tints()

    def set_environment_id(self, env_id: str) -> None:
        idx = self._environment.findData(env_id)
        if idx >= 0:
            self._environment.setCurrentIndex(idx)
        self._apply_environment_tints()

    def set_defaults(self, host_workdir: str, host_codex: str) -> None:
        if host_workdir:
            self._host_workdir.setText(host_workdir)
        if host_codex:
            self._host_codex_dir = host_codex

    def set_interactive_defaults(self, terminal_id: str, command: str) -> None:
        if command:
            self._command.setText(command)
        terminal_id = str(terminal_id or "")
        if terminal_id:
            idx = self._terminal.findData(terminal_id)
            if idx >= 0:
                self._terminal.setCurrentIndex(idx)

    def get_defaults(self) -> tuple[str, str]:
        host_workdir = os.path.expanduser((self._host_workdir.text() or "").strip())
        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())
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
        self._agent_cli_args = QLineEdit()
        self._agent_cli_args.setPlaceholderText("--model … (optional)")
        self._agent_cli_args.setToolTip(
            "Extra CLI flags appended to the agent command inside the container."
        )

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
        grid.addWidget(QLabel("Agent CLI Flags"), 4, 0)
        grid.addWidget(self._agent_cli_args, 4, 1, 1, 2)

        general_layout.addLayout(grid)

        self._preflight_enabled = QCheckBox("Enable environment preflight bash (runs after Settings preflight)")
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
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
            self._agent_cli_args.setText("")
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
        self._agent_cli_args.setText(env.agent_cli_args)
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
            agent_cli_args=base.agent_cli_args if base else "",
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
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
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
            agent_cli_args=agent_cli_args,
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
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
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
            agent_cli_args=agent_cli_args,
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
        grid.setColumnStretch(1, 1)

        self._use = QComboBox()
        self._use.addItem("Codex", "codex")
        self._use.addItem("Claude", "claude")
        self._use.addItem("GitHub Copilot", "copilot")

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._host_codex_dir = QLineEdit()
        self._host_codex_dir.setPlaceholderText(os.path.expanduser("~/.codex"))
        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(100)
        browse_codex.clicked.connect(self._pick_codex_dir)

        self._host_claude_dir = QLineEdit()
        self._host_claude_dir.setPlaceholderText(os.path.expanduser("~/.claude"))
        browse_claude = QPushButton("Browse…")
        browse_claude.setFixedWidth(100)
        browse_claude.clicked.connect(self._pick_claude_dir)

        self._host_copilot_dir = QLineEdit()
        self._host_copilot_dir.setPlaceholderText(os.path.expanduser("~/.copilot"))
        browse_copilot = QPushButton("Browse…")
        browse_copilot.setFixedWidth(100)
        browse_copilot.clicked.connect(self._pick_copilot_dir)

        self._preflight_enabled = QCheckBox("Enable settings preflight bash (runs on all envs, before env preflight)")
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before environment preflight (if enabled).\n"
            "# This script is mounted read-only and deleted from the host after the task finishes.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        grid.addWidget(QLabel("Agent CLI"), 0, 0)
        grid.addWidget(self._use, 0, 1)
        grid.addWidget(QLabel("Shell"), 0, 2)
        grid.addWidget(self._shell, 0, 3)
        codex_label = QLabel("Codex Config folder")
        claude_label = QLabel("Claude Config folder")
        copilot_label = QLabel("Copilot Config folder")

        grid.addWidget(codex_label, 1, 0)
        grid.addWidget(self._host_codex_dir, 1, 1, 1, 2)
        grid.addWidget(browse_codex, 1, 3)
        grid.addWidget(claude_label, 2, 0)
        grid.addWidget(self._host_claude_dir, 2, 1, 1, 2)
        grid.addWidget(browse_claude, 2, 3)
        grid.addWidget(copilot_label, 3, 0)
        grid.addWidget(self._host_copilot_dir, 3, 1, 1, 2)
        grid.addWidget(browse_copilot, 3, 3)
        grid.addWidget(self._preflight_enabled, 4, 0, 1, 4)

        self._agent_config_widgets: dict[str, tuple[QWidget, ...]] = {
            "codex": (codex_label, self._host_codex_dir, browse_codex),
            "claude": (claude_label, self._host_claude_dir, browse_claude),
            "copilot": (copilot_label, self._host_copilot_dir, browse_copilot),
        }
        self._use.currentIndexChanged.connect(self._sync_agent_config_widgets)
        self._sync_agent_config_widgets()

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
        use_value = normalize_agent(str(settings.get("use") or "codex"))
        self._set_combo_value(self._use, use_value, fallback="codex")
        self._sync_agent_config_widgets()

        shell_value = str(settings.get("shell") or "bash").strip().lower()
        self._set_combo_value(self._shell, shell_value, fallback="bash")

        host_codex_dir = os.path.expanduser(str(settings.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        self._host_codex_dir.setText(host_codex_dir)

        host_claude_dir = os.path.expanduser(str(settings.get("host_claude_dir") or "").strip())
        self._host_claude_dir.setText(host_claude_dir)

        host_copilot_dir = os.path.expanduser(str(settings.get("host_copilot_dir") or "").strip())
        self._host_copilot_dir.setText(host_copilot_dir)

        enabled = bool(settings.get("preflight_enabled") or False)
        self._preflight_enabled.setChecked(enabled)
        self._preflight_script.setEnabled(enabled)
        self._preflight_script.setPlainText(str(settings.get("preflight_script") or ""))

    def get_settings(self) -> dict:
        return {
            "use": str(self._use.currentData() or "codex"),
            "shell": str(self._shell.currentData() or "bash"),
            "host_codex_dir": os.path.expanduser(str(self._host_codex_dir.text() or "").strip()),
            "host_claude_dir": os.path.expanduser(str(self._host_claude_dir.text() or "").strip()),
            "host_copilot_dir": os.path.expanduser(str(self._host_copilot_dir.text() or "").strip()),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
        }

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Config folder",
            self._host_codex_dir.text() or os.path.expanduser("~/.codex"),
        )
        if path:
            self._host_codex_dir.setText(path)

    def _pick_claude_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Claude Config folder",
            self._host_claude_dir.text() or os.path.expanduser("~/.claude"),
        )
        if path:
            self._host_claude_dir.setText(path)

    def _pick_copilot_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Copilot Config folder",
            self._host_copilot_dir.text() or os.path.expanduser("~/.copilot"),
        )
        if path:
            self._host_copilot_dir.setText(path)

    def _on_save(self) -> None:
        self.saved.emit(self.get_settings())

    def _on_test_preflight(self) -> None:
        self.test_preflight_requested.emit(self.get_settings())

    def _sync_agent_config_widgets(self) -> None:
        use_value = normalize_agent(str(self._use.currentData() or "codex"))
        for agent, widgets in self._agent_config_widgets.items():
            visible = agent == use_value
            for widget in widgets:
                widget.setVisible(visible)

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
        self.setMinimumSize(1024, 640)
        self.resize(1280, 720)

        self._settings_data: dict[str, object] = {
            "use": "codex",
            "shell": "bash",
            "preflight_enabled": False,
            "preflight_script": "",
            "host_workdir": os.environ.get("CODEX_HOST_WORKDIR", os.getcwd()),
            "host_codex_dir": os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")),
            "host_claude_dir": "",
            "host_copilot_dir": "",
            "active_environment_id": "default",
            "interactive_terminal_id": "",
            "interactive_command": "--sandbox danger-full-access",
            "interactive_command_claude": "--add-dir /home/midori-ai/workspace",
            "interactive_command_copilot": "--add-dir /home/midori-ai/workspace",
            "window_w": 1280,
            "window_h": 720,
        }
        self._environments: dict[str, Environment] = {}
        self._syncing_environment = False
        self._tasks: dict[str, Task] = {}
        self._threads: dict[str, QThread] = {}
        self._bridges: dict[str, TaskRunnerBridge] = {}
        self._run_started_s: dict[str, float] = {}
        self._dashboard_log_refresh_s: dict[str, float] = {}
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

        self._btn_home = QToolButton()
        self._btn_home.setText("Home")
        self._btn_home.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_home.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self._btn_home.clicked.connect(self._show_dashboard)

        self._btn_new = QToolButton()
        self._btn_new.setText("New task")
        self._btn_new.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self._btn_new.clicked.connect(self._show_new_task)

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

        top_layout.addWidget(self._btn_home)
        top_layout.addWidget(self._btn_new)
        top_layout.addWidget(self._btn_envs)
        top_layout.addWidget(self._btn_settings)
        top_layout.addStretch(1)

        outer.addWidget(top)

        self._dashboard = DashboardPage()
        self._dashboard.task_selected.connect(self._open_task_details)
        self._dashboard.clean_old_requested.connect(self._clean_old_tasks)
        self._dashboard.task_discard_requested.connect(self._discard_task_from_ui)
        self._new_task = NewTaskPage()
        self._new_task.requested_run.connect(self._start_task_from_ui)
        self._new_task.requested_launch.connect(self._start_interactive_task_from_ui)
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
        self._apply_window_prefs()
        self._reload_environments()
        self._apply_settings_to_pages()

    def _apply_window_prefs(self) -> None:
        try:
            w = int(self._settings_data.get("window_w") or 1280)
            h = int(self._settings_data.get("window_h") or 720)
        except Exception:
            w, h = 1280, 720
        w = max(int(self.minimumWidth()), w)
        h = max(int(self.minimumHeight()), h)
        self.resize(w, h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._settings_data["window_w"] = int(self.width())
        self._settings_data["window_h"] = int(self.height())
        if hasattr(self, "_save_timer"):
            self._schedule_save()

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
        merged["use"] = normalize_agent(str(merged.get("use") or "codex"))

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        host_codex_dir = os.path.expanduser(str(merged.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        merged["host_codex_dir"] = host_codex_dir

        merged["host_claude_dir"] = os.path.expanduser(str(merged.get("host_claude_dir") or "").strip())
        merged["host_copilot_dir"] = os.path.expanduser(str(merged.get("host_copilot_dir") or "").strip())

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_command"] = str(merged.get("interactive_command") or "--sandbox danger-full-access")
        merged["interactive_command_claude"] = str(merged.get("interactive_command_claude") or "")
        merged["interactive_command_copilot"] = str(merged.get("interactive_command_copilot") or "")
        self._settings_data = merged
        self._apply_settings_to_pages()
        self._schedule_save()

    def _interactive_command_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "interactive_command_claude"
        if agent_cli == "copilot":
            return "interactive_command_copilot"
        return "interactive_command"

    def _host_config_dir_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "host_claude_dir"
        if agent_cli == "copilot":
            return "host_copilot_dir"
        return "host_codex_dir"

    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "copilot":
            return "--add-dir /home/midori-ai/workspace"
        return "--sandbox danger-full-access"

    def _effective_host_config_dir(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        agent_cli = normalize_agent(agent_cli)
        settings = settings or self._settings_data

        config_dir = ""
        if agent_cli == "claude":
            config_dir = str(settings.get("host_claude_dir") or "")
        elif agent_cli == "copilot":
            config_dir = str(settings.get("host_copilot_dir") or "")
        else:
            config_dir = str(
                settings.get("host_codex_dir")
                or os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex"))
            )
        if env and env.host_codex_dir:
            config_dir = env.host_codex_dir
        return os.path.expanduser(str(config_dir or "").strip())

    def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool:
        agent_cli = normalize_agent(agent_cli)
        host_config_dir = os.path.expanduser(str(host_config_dir or "").strip())
        if agent_cli in {"claude", "copilot"} and not host_config_dir:
            agent_label = "Claude" if agent_cli == "claude" else "Copilot"
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"Set the {agent_label} Config folder in Settings (or override it per-environment).",
            )
            return False
        if not host_config_dir:
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(self, "Invalid config folder", "Config folder path is not a directory.")
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True

    def _active_environment_id(self) -> str:
        return str(self._settings_data.get("active_environment_id") or "default")

    def _environment_list(self) -> list[Environment]:
        return sorted(self._environments.values(), key=lambda e: (e.name or e.env_id).lower())

    def _populate_environment_pickers(self) -> None:
        active_id = self._active_environment_id()
        envs = self._environment_list()
        stains = {e.env_id: e.color for e in envs}

        self._new_task.set_environment_stains(stains)
        self._dashboard.set_environment_filter_options([(e.env_id, e.name or e.env_id) for e in envs])

        self._syncing_environment = True
        try:
            self._new_task.set_environments([(e.env_id, e.name or e.env_id) for e in envs], active_id=active_id)
            self._new_task.set_environment_id(active_id)
        finally:
            self._syncing_environment = False

    def _apply_active_environment_to_new_task(self) -> None:
        env = self._environments.get(self._active_environment_id())
        host_workdir = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if env:
            if env.host_workdir:
                host_workdir = env.host_workdir
        self._new_task.set_defaults(host_workdir=host_workdir, host_codex=host_codex)
        interactive_key = self._interactive_command_key(agent_cli)
        interactive_command = str(self._settings_data.get(interactive_key) or "").strip()
        if not interactive_command:
            interactive_command = self._default_interactive_command(agent_cli)
        self._new_task.set_interactive_defaults(
            terminal_id=str(self._settings_data.get("interactive_terminal_id") or ""),
            command=interactive_command,
        )
        self._populate_environment_pickers()

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
            self._dashboard_log_refresh_s.pop(task_id, None)
        self._schedule_save()

    def _start_task_from_ui(self, prompt: str, host_workdir: str, host_codex: str, env_id: str) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return
        prompt = sanitize_prompt((prompt or "").strip())

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        self._settings_data["host_workdir"] = host_workdir

        task_id = uuid4().hex[:10]
        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        self._settings_data["active_environment_id"] = env_id
        env = self._environments.get(env_id)
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return
        self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex

        image = PIXELARCH_EMERALD_IMAGE

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
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
            agent_cli=agent_cli,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            agent_cli_args=agent_cli_args,
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

    def _start_interactive_task_from_ui(
        self,
        prompt: str,
        command: str,
        host_workdir: str,
        host_codex: str,
        env_id: str,
        terminal_id: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        prompt = sanitize_prompt((prompt or "").strip())
        host_workdir = os.path.expanduser((host_workdir or "").strip())
        host_codex = os.path.expanduser((host_codex or "").strip())
        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        opt = options.get(str(terminal_id or "").strip())
        if opt is None:
            QMessageBox.warning(
                self,
                "Terminal not available",
                "The selected terminal could not be found. Click Refresh next to Terminal and pick again.",
            )
            return

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        env = self._environments.get(env_id)

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        command = str(command or "").strip() or "bash"
        try:
            if command.startswith("-"):
                cmd_parts = [agent_cli, *shlex.split(command)]
            else:
                cmd_parts = shlex.split(command)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid container command", str(exc))
            return
        if not cmd_parts:
            cmd_parts = ["bash"]

        def _move_positional_to_end(parts: list[str], value: str) -> None:
            value = str(value or "")
            if not value:
                return
            for idx in range(len(parts) - 1, 0, -1):
                if parts[idx] != value:
                    continue
                prev = parts[idx - 1]
                if prev != "--" and prev.startswith("-"):
                    continue
                parts.pop(idx)
                break
            parts.append(value)

        def _move_flag_value_to_end(parts: list[str], flags: set[str]) -> None:
            for idx in range(len(parts) - 2, -1, -1):
                if parts[idx] in flags:
                    flag = parts.pop(idx)
                    value = parts.pop(idx)
                    parts.extend([flag, value])
                    return

        if cmd_parts[0] == "codex":
            if len(cmd_parts) >= 2 and cmd_parts[1] == "exec":
                cmd_parts.pop(1)
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "claude":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "copilot":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                has_interactive = "-i" in cmd_parts or "--interactive" in cmd_parts
                has_prompt = "-p" in cmd_parts or "--prompt" in cmd_parts
                if has_prompt:
                    _move_flag_value_to_end(cmd_parts, {"-p", "--prompt"})
                elif not has_interactive:
                    cmd_parts.extend(["-i", prompt])

        image = PIXELARCH_EMERALD_IMAGE

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        task_token = f"interactive-{uuid4().hex[:8]}"
        container_name = f"codex-gui-it-{uuid4().hex[:10]}"
        container_agent_dir = container_config_dir(agent_cli)
        config_extra_mounts = additional_config_mounts(agent_cli, host_codex)
        container_workdir = "/home/midori-ai/workspace"

        settings_tmp_path = ""
        env_tmp_path = ""

        preflight_clause = ""
        preflight_mounts: list[str] = []
        settings_container_path = f"/tmp/codex-preflight-settings-{task_token}.sh"
        environment_container_path = f"/tmp/codex-preflight-environment-{task_token}.sh"

        def _write_preflight_script(script: str, label: str) -> str:
            fd, tmp_path = tempfile.mkstemp(prefix=f"codex-preflight-{label}-{task_token}-", suffix=".sh")
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
            return tmp_path

        try:
            if (settings_preflight_script or "").strip():
                settings_tmp_path = _write_preflight_script(str(settings_preflight_script or ""), "settings")
                preflight_mounts.extend(["-v", f"{settings_tmp_path}:{settings_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; '
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if (environment_preflight_script or "").strip():
                env_tmp_path = _write_preflight_script(str(environment_preflight_script or ""), "environment")
                preflight_mounts.extend(["-v", f"{env_tmp_path}:{environment_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_ENV={shlex.quote(environment_container_path)}; '
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            QMessageBox.warning(self, "Failed to prepare preflight scripts", str(exc))
            return

        try:
            env_args: list[str] = []
            for key, value in sorted((env.env_vars or {}).items() if env else []):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            extra_mount_args: list[str] = []
            for mount in (env.extra_mounts or []) if env else []:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            for mount in config_extra_mounts:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])

            target_cmd = " ".join(shlex.quote(part) for part in cmd_parts)
            verify_clause = ""
            if cmd_parts[0] in {"codex", "claude", "copilot"}:
                verify_clause = verify_cli_clause(cmd_parts[0])

            container_script = "set -euo pipefail; " f"{preflight_clause}{verify_clause}{target_cmd}"

            docker_args = [
                "docker",
                "run",
                "-it",
                "--name",
                container_name,
                "-v",
                f"{host_codex}:{container_agent_dir}",
                "-v",
                f"{host_workdir}:{container_workdir}",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                "-w",
                container_workdir,
                image,
                "/bin/bash",
                "-lc",
                container_script,
            ]
            docker_cmd = " ".join(shlex.quote(part) for part in docker_args)

            host_script = " ; ".join(
                [
                    f'CONTAINER_NAME={shlex.quote(container_name)}',
                    f'TMP_SETTINGS={shlex.quote(settings_tmp_path)}',
                    f'TMP_ENV={shlex.quote(env_tmp_path)}',
                    'cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; '
                    'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
                    'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; }',
                    "trap cleanup EXIT",
                    f"docker pull {shlex.quote(image)} || {{ STATUS=$?; echo \"[host] docker pull failed (exit $STATUS)\"; read -r -p \"Press Enter to close...\"; exit $STATUS; }}",
                    f"{docker_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then echo \"[host] container command failed (exit $STATUS)\"; read -r -p \"Press Enter to close...\"; fi; exit $STATUS",
                ]
            )

            self._settings_data["host_workdir"] = host_workdir
            self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex
            self._settings_data["active_environment_id"] = env_id
            self._settings_data["interactive_terminal_id"] = str(terminal_id or "")
            self._settings_data[self._interactive_command_key(agent_cli)] = command
            self._apply_active_environment_to_new_task()
            self._schedule_save()

            launch_in_terminal(opt, host_script, cwd=host_workdir)
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            QMessageBox.warning(self, "Failed to launch terminal", str(exc))

    def _start_preflight_task(
        self,
        *,
        label: str,
        env: Environment,
        agent_cli: str | None,
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

        agent_cli = normalize_agent(str(agent_cli or self._settings_data.get("use") or "codex"))
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
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
            agent_cli=agent_cli,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            agent_cli_args=[],
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
        settings_enabled = bool(settings.get("preflight_enabled") or False)
        settings_script: str | None = None
        if settings_enabled:
            candidate = str(settings.get("preflight_script") or "")
            if candidate.strip():
                settings_script = candidate

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(settings.get("use") or self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None, settings=settings)

        if settings_script is None:
            has_env_preflights = any(
                e.preflight_enabled and (e.preflight_script or "").strip() for e in self._environment_list()
            )
            if not has_env_preflights:
                if not settings_enabled:
                    return
                QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
                return

        skipped: list[str] = []
        started = 0
        for env in self._environment_list():
            env_script: str | None = None
            candidate = str(env.preflight_script or "")
            if env.preflight_enabled and candidate.strip():
                env_script = candidate

            if settings_script is None and env_script is None:
                continue

            host_workdir = env.host_workdir or host_workdir_base
            host_codex = env.host_codex_dir or host_codex_base
            if not os.path.isdir(host_workdir):
                skipped.append(f"{env.name or env.env_id} ({host_workdir})")
                continue
            self._start_preflight_task(
                label=f"Preflight test (all): {env.name or env.env_id}",
                env=env,
                agent_cli=agent_cli,
                host_workdir=host_workdir,
                host_codex=host_codex,
                settings_preflight_script=settings_script,
                environment_preflight_script=env_script,
            )
            started += 1

        if started == 0 and not skipped:
            if not settings_enabled:
                return
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

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
        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None)
        host_workdir = env.host_workdir or host_workdir_base
        host_codex = env.host_codex_dir or host_codex_base

        self._start_preflight_task(
            label=f"Preflight test: {env.name or env.env_id}",
            env=env,
            agent_cli=agent_cli,
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

    def _discard_task_from_ui(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            return

        prompt = task.prompt_one_line()
        message = (
            f"Discard task {task_id}?\n\n"
            f"{prompt}\n\n"
            "This removes it from the list and will attempt to stop/remove any running container."
        )
        if QMessageBox.question(self, "Discard task?", message) != QMessageBox.StandardButton.Yes:
            return

        bridge = self._bridges.get(task_id)
        thread = self._threads.get(task_id)
        container_id = task.container_id or (bridge.container_id if bridge is not None else None)

        if bridge is not None:
            try:
                QMetaObject.invokeMethod(bridge, "request_stop", Qt.QueuedConnection)
            except Exception:
                pass
        if thread is not None:
            try:
                thread.quit()
            except Exception:
                pass

        self._dashboard.remove_tasks({task_id})
        self._tasks.pop(task_id, None)
        self._threads.pop(task_id, None)
        self._bridges.pop(task_id, None)
        self._run_started_s.pop(task_id, None)
        self._dashboard_log_refresh_s.pop(task_id, None)
        self._schedule_save()

        if self._details.isVisible() and self._details.current_task_id() == task_id:
            self._show_dashboard()

        if container_id:
            threading.Thread(
                target=self._force_remove_container,
                args=(container_id,),
                daemon=True,
            ).start()

    @staticmethod
    def _force_remove_container(container_id: str) -> None:
        container_id = str(container_id or "").strip()
        if not container_id:
            return
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=25.0,
            )
        except Exception:
            pass

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
        if cleaned and self._dashboard.isVisible() and task.is_active():
            now_s = time.time()
            last_s = float(self._dashboard_log_refresh_s.get(task_id) or 0.0)
            if now_s - last_s >= 0.25:
                self._dashboard_log_refresh_s[task_id] = now_s
                env = self._environments.get(task.environment_id)
                stain = env.color if env else None
                spinner = _stain_color(env.color) if env else None
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
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
        self._settings_data["use"] = normalize_agent(str(self._settings_data.get("use") or "codex"))
        self._settings_data.setdefault("host_claude_dir", "")
        self._settings_data.setdefault("host_copilot_dir", "")
        self._settings_data.setdefault("interactive_command_claude", "--add-dir /home/midori-ai/workspace")
        self._settings_data.setdefault("interactive_command_copilot", "--add-dir /home/midori-ai/workspace")
        host_codex_dir = os.path.normpath(os.path.expanduser(str(self._settings_data.get("host_codex_dir") or "").strip()))
        if host_codex_dir == os.path.expanduser("~/.midoriai"):
            self._settings_data["host_codex_dir"] = os.path.expanduser("~/.codex")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            raw = str(self._settings_data.get(key) or "").strip()
            if not raw:
                continue
            try:
                cmd_parts = shlex.split(raw)
            except ValueError:
                cmd_parts = []
            if cmd_parts and cmd_parts[0] in {"codex", "claude", "copilot"}:
                head = cmd_parts.pop(0)
                if head == "codex" and cmd_parts and cmd_parts[0] == "exec":
                    cmd_parts.pop(0)
                self._settings_data[key] = " ".join(shlex.quote(part) for part in cmd_parts)
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
