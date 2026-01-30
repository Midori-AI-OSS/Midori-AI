from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QFormLayout
from PySide6.QtWidgets import QGroupBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSlider
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from config import CONFIG
from config import reload_config_from_disk
from config import save_current_config


@dataclass(frozen=True)
class _SliderSpec:
    label: str
    min_v: float
    max_v: float
    step: float
    getter: callable
    setter: callable
    fmt: str = "{:.3f}"

@dataclass(frozen=True)
class _SliderRowState:
    spec: _SliderSpec
    scale: float
    slider: QSlider
    value: QLabel


def _slider_row(spec: _SliderSpec) -> tuple[QWidget, _SliderRowState]:
    scale = 1.0 / float(spec.step)
    s_min = int(round(float(spec.min_v) * scale))
    s_max = int(round(float(spec.max_v) * scale))
    initial = float(spec.getter())
    s_init = int(round(initial * scale))

    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    name = QLabel(spec.label)
    name.setMinimumWidth(150)

    val = QLabel(spec.fmt.format(initial))
    val.setProperty("role", "dim")
    val.setMinimumWidth(64)
    val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    slider = QSlider(Qt.Horizontal)
    slider.setMinimum(s_min)
    slider.setMaximum(s_max)
    slider.setValue(s_init)

    def _changed(v: int) -> None:
        f = float(v) / scale
        spec.setter(f)
        val.setText(spec.fmt.format(float(spec.getter())))

    slider.valueChanged.connect(_changed)

    row.addWidget(name)
    row.addWidget(slider, 1)
    row.addWidget(val)
    state = _SliderRowState(spec=spec, scale=scale, slider=slider, value=val)
    return w, state


class SettingsOverlay(QWidget):
    def __init__(self, *, on_apply, on_close, parent=None) -> None:
        super().__init__(parent=parent)
        self._on_apply = on_apply
        self._on_close = on_close

        self.setObjectName("mainMenuPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("fullScreen", True)
        self.setProperty("mode", "settings")

        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Settings")
        title.setStyleSheet("font-weight: 800; font-size: 18px;")
        header.addWidget(title)
        header.addStretch(1)
        self._status = QLabel("")
        self._status.setProperty("role", "dim")
        header.addWidget(self._status)
        panel_layout.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        panel_layout.addWidget(scroll, 1)

        body = QWidget()
        scroll.setWidget(body)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        self._rows: list[_SliderRowState] = []
        body_layout.addWidget(self._group_gameplay())
        body_layout.addWidget(self._group_spawning())
        body_layout.addWidget(self._group_foes())
        body_layout.addWidget(self._group_projectiles())
        body_layout.addWidget(self._group_render())
        body_layout.addStretch(1)

        panel_layout.addWidget(self._actions_row())

        self.refresh_from_config()

    def _actions_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        apply_btn = QPushButton("Apply")
        apply_btn.setProperty("stainedMenu", "true")
        apply_btn.clicked.connect(self.apply_changes)

        save_btn = QPushButton("Save to config.py")
        save_btn.setProperty("stainedMenu", "true")
        save_btn.clicked.connect(self._save)

        reload_btn = QPushButton("Reload config.py")
        reload_btn.setProperty("stainedMenu", "true")
        reload_btn.clicked.connect(self._reload)

        close_btn = QPushButton("Close")
        close_btn.setProperty("stainedMenu", "true")
        close_btn.clicked.connect(self._on_close)

        row.addWidget(apply_btn)
        row.addWidget(save_btn)
        row.addWidget(reload_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        return w

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def apply_changes(self) -> None:
        self._set_status("")
        self._on_apply()
        self._set_status("Applied")

    def _save(self) -> None:
        try:
            save_current_config()
        except Exception as exc:  # noqa: BLE001 - surface message in UI
            self._set_status(f"Save failed: {exc}")
            return
        self._set_status("Saved to config.py")

    def _reload(self) -> None:
        try:
            reload_config_from_disk()
        except Exception as exc:  # noqa: BLE001 - surface message in UI
            self._set_status(f"Reload failed: {exc}")
            return
        self.refresh_from_config()
        self._on_apply()
        self._set_status("Reloaded from config.py")

    def refresh_from_config(self) -> None:
        for row in self._rows:
            spec = row.spec
            slider = row.slider
            val = row.value
            target = int(round(float(spec.getter()) * float(row.scale)))
            slider.blockSignals(True)
            slider.setValue(target)
            slider.blockSignals(False)
            val.setText(spec.fmt.format(float(spec.getter())))

    def _group_gameplay(self) -> QGroupBox:
        box = QGroupBox("Gameplay")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row, state = _slider_row(
            _SliderSpec(
                label="Player HP",
                min_v=100.0,
                max_v=50_000.0,
                step=50.0,
                getter=lambda: float(CONFIG.player.start_hp),
                setter=lambda v: setattr(CONFIG.player, "start_hp", float(v)),
                fmt="{:.0f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)
        return box

    def _group_spawning(self) -> QGroupBox:
        box = QGroupBox("Spawning")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row, state = _slider_row(
            _SliderSpec(
                label="Spawn interval (s)",
                min_v=0.05,
                max_v=10.0,
                step=0.05,
                getter=lambda: float(CONFIG.spawning.start_spawn_rate_s),
                setter=lambda v: setattr(CONFIG.spawning, "start_spawn_rate_s", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Speedup / kill",
                min_v=0.0,
                max_v=0.12,
                step=0.002,
                getter=lambda: float(CONFIG.spawning.spawn_speedup_per_kill),
                setter=lambda v: setattr(CONFIG.spawning, "spawn_speedup_per_kill", float(v)),
                fmt="{:.3f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Soft target (visible)",
                min_v=10.0,
                max_v=500.0,
                step=10.0,
                getter=lambda: float(CONFIG.spawning.visible_foe_soft_target),
                setter=lambda v: setattr(CONFIG.spawning, "visible_foe_soft_target", int(round(v))),
                fmt="{:.0f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)
        return box

    def _group_foes(self) -> QGroupBox:
        box = QGroupBox("Foes")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row, state = _slider_row(
            _SliderSpec(
                label="Foe size",
                min_v=0.03,
                max_v=0.5,
                step=0.01,
                getter=lambda: float(CONFIG.render.foe_shape_scale),
                setter=lambda v: setattr(CONFIG.render, "foe_shape_scale", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Move speed",
                min_v=0.05,
                max_v=2.0,
                step=0.02,
                getter=lambda: float(CONFIG.foe.move_speed),
                setter=lambda v: setattr(CONFIG.foe, "move_speed", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Attack zone NDC Y",
                min_v=-0.95,
                max_v=-0.05,
                step=0.02,
                getter=lambda: float(CONFIG.foe.attack_zone_ndc_y),
                setter=lambda v: setattr(CONFIG.foe, "attack_zone_ndc_y", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Attack interval (s)",
                min_v=0.1,
                max_v=5.0,
                step=0.05,
                getter=lambda: float(CONFIG.foe.attack_interval_s),
                setter=lambda v: setattr(CONFIG.foe, "attack_interval_s", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Attack damage",
                min_v=1.0,
                max_v=250.0,
                step=1.0,
                getter=lambda: float(CONFIG.foe.attack_damage),
                setter=lambda v: setattr(CONFIG.foe, "attack_damage", float(v)),
                fmt="{:.0f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)
        return box

    def _group_projectiles(self) -> QGroupBox:
        box = QGroupBox("Projectiles")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row, state = _slider_row(
            _SliderSpec(
                label="Fire interval (s)",
                min_v=0.03,
                max_v=1.0,
                step=0.01,
                getter=lambda: float(CONFIG.projectile.fire_rate_s),
                setter=lambda v: setattr(CONFIG.projectile, "fire_rate_s", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Projectile speed",
                min_v=0.5,
                max_v=10.0,
                step=0.1,
                getter=lambda: float(CONFIG.projectile.speed),
                setter=lambda v: setattr(CONFIG.projectile, "speed", float(v)),
                fmt="{:.1f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Projectile damage",
                min_v=1.0,
                max_v=250.0,
                step=1.0,
                getter=lambda: float(CONFIG.projectile.damage),
                setter=lambda v: setattr(CONFIG.projectile, "damage", float(v)),
                fmt="{:.0f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)
        return box

    def _group_render(self) -> QGroupBox:
        box = QGroupBox("Render")
        f = QFormLayout(box)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row, state = _slider_row(
            _SliderSpec(
                label="Point size",
                min_v=1.0,
                max_v=24.0,
                step=0.25,
                getter=lambda: float(CONFIG.render.point_size),
                setter=lambda v: setattr(CONFIG.render, "point_size", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Softness",
                min_v=1.0,
                max_v=22.0,
                step=0.25,
                getter=lambda: float(CONFIG.render.softness),
                setter=lambda v: setattr(CONFIG.render, "softness", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Exposure",
                min_v=0.1,
                max_v=4.0,
                step=0.05,
                getter=lambda: float(CONFIG.render.exposure),
                setter=lambda v: setattr(CONFIG.render, "exposure", float(v)),
                fmt="{:.2f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)

        row, state = _slider_row(
            _SliderSpec(
                label="Depth fade",
                min_v=0.0,
                max_v=0.45,
                step=0.005,
                getter=lambda: float(CONFIG.render.depth_fade),
                setter=lambda v: setattr(CONFIG.render, "depth_fade", float(v)),
                fmt="{:.3f}",
            )
        )
        self._rows.append(state)
        f.addRow(row)
        return box
