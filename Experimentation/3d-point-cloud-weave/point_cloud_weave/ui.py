from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QDockWidget
from PySide6.QtWidgets import QFormLayout
from PySide6.QtWidgets import QGroupBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QSlider
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from point_cloud_weave.gl_widget import WeaveGLWidget
from point_cloud_weave.profile import ProfilerController
from point_cloud_weave.sim import WeaveSim


@dataclass(frozen=True)
class AppPaths:
    render_dir: Path
    profile_dir: Path


def _slider_row(
    *,
    label: str,
    min_v: float,
    max_v: float,
    step: float,
    initial: float,
    on_change: callable,
) -> QWidget:
    scale = 1.0 / float(step)
    s_min = int(round(min_v * scale))
    s_max = int(round(max_v * scale))
    s_init = int(round(initial * scale))

    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)

    name = QLabel(label)
    name.setMinimumWidth(140)

    val = QLabel(f"{initial:.3f}")
    val.setProperty("role", "dim")
    val.setMinimumWidth(60)
    val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    slider = QSlider(Qt.Horizontal)
    slider.setMinimum(s_min)
    slider.setMaximum(s_max)
    slider.setValue(s_init)

    def _changed(v: int) -> None:
        f = float(v) / scale
        val.setText(f"{f:.3f}")
        on_change(f)

    slider.valueChanged.connect(_changed)

    row.addWidget(name)
    row.addWidget(slider, 1)
    row.addWidget(val)
    return w


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        sim: WeaveSim,
        profiler: ProfilerController,
        paths: AppPaths,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.paths = paths
        self.profiler = profiler

        self.setWindowTitle("3D Point Cloud Weave")
        self.resize(1100, 780)

        self.gl = WeaveGLWidget(sim=sim, profiler=profiler, on_profile_saved=self._profile_saved)
        self.setCentralWidget(self.gl)

        self._init_dock()
        self.statusBar().showMessage(f"Points: {sim.n_points} | Device: {sim.device.type}")

    def _profile_saved(self, path: Path) -> None:
        self.statusBar().showMessage(f"Profile saved: {path}")

    def _init_dock(self) -> None:
        dock = QDockWidget("Controls", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        body = QWidget()
        body.setObjectName("mainMenuPanel")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        layout.addWidget(self._group_render())
        layout.addWidget(self._group_motion())
        layout.addWidget(self._group_disrupt())
        layout.addWidget(self._group_mouse())
        layout.addWidget(self._group_actions())
        layout.addStretch(1)

        dock.setWidget(body)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _group_render(self) -> QGroupBox:
        box = QGroupBox("Render")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        f.addRow(
            _slider_row(
                label="Point size",
                min_v=1.0,
                max_v=24.0,
                step=0.25,
                initial=self.gl.render.point_size,
                on_change=lambda v: setattr(self.gl.render, "point_size", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Softness",
                min_v=1.0,
                max_v=22.0,
                step=0.25,
                initial=self.gl.render.softness,
                on_change=lambda v: setattr(self.gl.render, "softness", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Exposure",
                min_v=0.1,
                max_v=3.0,
                step=0.02,
                initial=self.gl.render.exposure,
                on_change=lambda v: setattr(self.gl.render, "exposure", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Depth fade",
                min_v=0.0,
                max_v=0.45,
                step=0.005,
                initial=self.gl.render.depth_fade,
                on_change=lambda v: setattr(self.gl.render, "depth_fade", v),
            )
        )
        return box

    def _group_motion(self) -> QGroupBox:
        box = QGroupBox("Motion")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        f.addRow(
            _slider_row(
                label="Speed gain",
                min_v=0.1,
                max_v=4.0,
                step=0.02,
                initial=self.gl.sim.params.speed_gain,
                on_change=lambda v: setattr(self.gl.sim.params, "speed_gain", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Speed cap",
                min_v=0.1,
                max_v=6.0,
                step=0.02,
                initial=self.gl.sim.params.speed_cap,
                on_change=lambda v: setattr(self.gl.sim.params, "speed_cap", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Accel",
                min_v=1.0,
                max_v=30.0,
                step=0.2,
                initial=self.gl.sim.params.accel,
                on_change=lambda v: setattr(self.gl.sim.params, "accel", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Damping",
                min_v=0.1,
                max_v=8.0,
                step=0.05,
                initial=self.gl.sim.params.damping,
                on_change=lambda v: setattr(self.gl.sim.params, "damping", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Activation fade",
                min_v=0.05,
                max_v=3.0,
                step=0.02,
                initial=self.gl.sim.params.activation_fade_s,
                on_change=lambda v: setattr(self.gl.sim.params, "activation_fade_s", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Swirl",
                min_v=0.0,
                max_v=1.0,
                step=0.01,
                initial=self.gl.sim.params.swirl_strength,
                on_change=lambda v: setattr(self.gl.sim.params, "swirl_strength", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Spawn noise",
                min_v=0.0,
                max_v=0.25,
                step=0.002,
                initial=self.gl.sim.params.noise_strength,
                on_change=lambda v: setattr(self.gl.sim.params, "noise_strength", v),
            )
        )
        return box

    def _group_disrupt(self) -> QGroupBox:
        box = QGroupBox("Disruption")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        f.addRow(
            _slider_row(
                label="Strength",
                min_v=0.0,
                max_v=3.0,
                step=0.02,
                initial=self.gl.sim.params.disrupt_strength,
                on_change=lambda v: setattr(self.gl.sim.params, "disrupt_strength", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Probability",
                min_v=0.0,
                max_v=0.5,
                step=0.005,
                initial=self.gl.sim.params.disrupt_prob,
                on_change=lambda v: setattr(self.gl.sim.params, "disrupt_prob", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Radius",
                min_v=0.1,
                max_v=6.0,
                step=0.05,
                initial=self.gl.sim.params.disrupt_radius,
                on_change=lambda v: setattr(self.gl.sim.params, "disrupt_radius", v),
            )
        )
        return box

    def _group_mouse(self) -> QGroupBox:
        box = QGroupBox("Mouse Repel")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        f.addRow(
            _slider_row(
                label="Strength",
                min_v=0.0,
                max_v=10.0,
                step=0.05,
                initial=self.gl.sim.params.repel_strength,
                on_change=lambda v: setattr(self.gl.sim.params, "repel_strength", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Radius",
                min_v=0.05,
                max_v=3.0,
                step=0.01,
                initial=self.gl.sim.params.repel_radius,
                on_change=lambda v: setattr(self.gl.sim.params, "repel_radius", v),
            )
        )
        f.addRow(
            _slider_row(
                label="Falloff",
                min_v=0.05,
                max_v=2.0,
                step=0.01,
                initial=self.gl.sim.params.repel_sigma,
                on_change=lambda v: setattr(self.gl.sim.params, "repel_sigma", v),
            )
        )
        return box

    def _group_actions(self) -> QGroupBox:
        box = QGroupBox("Actions")
        row = QVBoxLayout(box)

        pause = QCheckBox("Pause")
        pause.stateChanged.connect(lambda s: setattr(self.gl.sim, "paused", s == Qt.Checked))

        reset = QPushButton("Reset particles")
        reset.setProperty("stainedMenu", "true")
        reset.clicked.connect(self.gl.reset_sim)

        screenshot = QPushButton("Screenshot")
        screenshot.setProperty("stainedMenu", "true")

        def _shot() -> None:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.gl.screenshot(self.paths.render_dir / f"weave-{ts}.png")
            self.statusBar().showMessage(f"Saved screenshot: {self.paths.render_dir}/weave-{ts}.png")

        screenshot.clicked.connect(_shot)

        profile_5s = QPushButton("Profile 5s")
        profile_5s.setProperty("stainedMenu", "true")

        def _profile() -> None:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.profiler.start(seconds=5.0, out_path=self.paths.profile_dir / f"profile-{ts}.pstats")
            self.statusBar().showMessage("Profiling for 5 seconds...")

        profile_5s.clicked.connect(_profile)

        row.addWidget(pause)
        row.addWidget(reset)
        row.addWidget(screenshot)
        row.addWidget(profile_5s)
        return box
