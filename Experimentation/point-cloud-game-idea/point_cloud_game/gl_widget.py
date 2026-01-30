from __future__ import annotations

import time

import moderngl
import numpy as np
import torch

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from config import CONFIG
from point_cloud_game.camera import TopDownCamera
from point_cloud_game.profile import ProfilerController
from point_cloud_game.sim import WeaveSim


@dataclass
class RenderParams:
    point_size: float = 7.0
    softness: float = 7.5
    depth_fade: float = 0.08
    exposure: float = 1.0


_POINT_VS = """
#version 330
in vec3 in_pos;
in vec3 in_color;
in float in_intensity;
in float in_activation;

uniform mat4 u_view;
uniform mat4 u_proj;
uniform float u_time;
uniform float u_point_size;
uniform float u_activation_fade;
uniform float u_depth_fade;
uniform float u_exposure;

out vec4 v_col;

void main() {
    vec4 view = u_view * vec4(in_pos, 1.0);
    gl_Position = u_proj * view;

    float depth = max(0.0, -view.z);
    float fade = exp(-depth * u_depth_fade);
    float act = smoothstep(in_activation, in_activation + u_activation_fade, u_time);
    float size = u_point_size / max(0.35, depth);

    gl_PointSize = size;
    v_col = vec4(in_color * in_intensity * fade * act * u_exposure, 1.0);
}
"""

_POINT_FS = """
#version 330
in vec4 v_col;

uniform float u_softness;

out vec4 f_col;

void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(p, p);
    float falloff = exp(-r2 * u_softness);

    f_col = vec4(v_col.rgb * falloff, 1.0);
}
"""


class WeaveGLWidget(QOpenGLWidget):
    def __init__(
        self,
        *,
        game,
        profiler: ProfilerController,
        on_profile_saved: Callable[[Path], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.game = game
        self.sim = game.manager.sim
        self.profiler = profiler
        self.on_profile_saved = on_profile_saved
        self.render = RenderParams()
        self.camera = TopDownCamera()

        self._ctx: moderngl.Context | None = None
        self._prog_points: moderngl.Program | None = None
        self._vao_points: moderngl.VertexArray | None = None
        self._buf_pos: moderngl.Buffer | None = None
        self._buf_static: moderngl.Buffer | None = None

        self._last_frame = time.perf_counter()

        self._scene_visible = True

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(0)

        self.apply_config()

    def set_scene_visible(self, visible: bool) -> None:
        self._scene_visible = bool(visible)
        if self.sim is not None:
            self.sim.paused = not self._scene_visible

    def reset_sim(self) -> None:
        seed = int(torch.randint(0, 2**31 - 1, (1,), device="cpu").item())
        self.sim.reset_state(seed=seed)

    def apply_config(self) -> None:
        self.render.point_size = float(CONFIG.render.point_size)
        self.render.softness = float(CONFIG.render.softness)
        self.render.depth_fade = float(CONFIG.render.depth_fade)
        self.render.exposure = float(CONFIG.render.exposure)

    def screenshot(self, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = self.grabFramebuffer()
        img.save(str(out_path))

    def initializeGL(self) -> None:
        self._ctx = moderngl.create_context(require=330, standalone=False)
        self._ctx.enable(moderngl.BLEND)
        self._ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self._ctx.blend_func = (moderngl.ONE, moderngl.ONE)

        self._prog_points = self._ctx.program(vertex_shader=_POINT_VS, fragment_shader=_POINT_FS)

        pos = self._pos_numpy()
        self._buf_pos = self._ctx.buffer(pos.tobytes(), dynamic=True)

        colors = self.sim.colors.detach().to("cpu").float().numpy()
        intensity = self.sim.intensity.detach().to("cpu").float().numpy()
        activation = self.sim.activation_time.detach().to("cpu").float().numpy()
        static = np.concatenate((colors, intensity[:, None], activation[:, None]), axis=1).astype(np.float32)
        self._buf_static = self._ctx.buffer(static.tobytes())

        self._vao_points = self._ctx.vertex_array(
            self._prog_points,
            [
                (self._buf_pos, "3f", "in_pos"),
                (self._buf_static, "3f 1f 1f", "in_color", "in_intensity", "in_activation"),
            ],
        )

        self._ctx.viewport = (0, 0, max(1, self.width()), max(1, self.height()))

    def resizeGL(self, width: int, height: int) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        width = max(1, int(width))
        height = max(1, int(height))
        ctx.viewport = (0, 0, width, height)

    def paintGL(self) -> None:
        ctx = self._ctx
        prog_points = self._prog_points
        vao_points = self._vao_points
        buf_pos = self._buf_pos
        if ctx is None or prog_points is None or vao_points is None or buf_pos is None:
            return

        pos = self._pos_numpy()
        buf_pos.write(pos.tobytes())

        width = max(1, self.width())
        height = max(1, self.height())
        aspect = width / height

        fbo = ctx.detect_framebuffer()
        fbo.use()
        ctx.viewport = (0, 0, width, height)
        if not self._scene_visible:
            fbo.clear(0.0, 0.0, 0.0, 1.0)
            return

        view = self.camera.view_matrix()
        proj = self.camera.proj_matrix(aspect)

        prog_points["u_view"].write(view.T.tobytes())
        prog_points["u_proj"].write(proj.T.tobytes())
        prog_points["u_time"].value = float(self.sim.time_s)
        prog_points["u_point_size"].value = float(self.render.point_size)
        prog_points["u_activation_fade"].value = float(self.sim.params.activation_fade_s)
        prog_points["u_softness"].value = float(self.render.softness)
        prog_points["u_depth_fade"].value = float(self.render.depth_fade)
        prog_points["u_exposure"].value = float(self.render.exposure)

        fbo.clear(0.0, 0.0, 0.0, 1.0)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.ONE, moderngl.ONE)
        vao_points.render(mode=moderngl.POINTS)

    def _pos_numpy(self) -> np.ndarray:
        pos = self.sim.pos
        if pos.device.type != "cpu":
            pos = pos.detach().to("cpu")
        return pos.detach().float().numpy().astype(np.float32, copy=False)

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last_frame
        self._last_frame = now
        dt = float(min(1 / 20.0, max(0.0, dt)))

        width = float(max(1, self.width()))
        height = float(max(1, self.height()))
        self.game.set_view(camera=self.camera, aspect=(width / height))
        self.game.update(dt)
        self.sim.step(dt)

        saved = self.profiler.stop_if_due()
        if saved is not None and self.on_profile_saved is not None:
            self.on_profile_saved(saved)

        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pass

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pass

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pass

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta != 0:
            self.camera.distance = float(np.clip(self.camera.distance * (0.92 ** (delta / 120.0)), 0.4, 20.0))
        super().wheelEvent(event)

    def _cursor_world(self, x: float, y: float) -> torch.Tensor | None:
        width = float(max(1, self.width()))
        height = float(max(1, self.height()))
        aspect = width / height

        view = self.camera.view_matrix()
        proj = self.camera.proj_matrix(aspect)
        inv = np.linalg.inv(proj @ view).astype(np.float32)

        nx = (float(x) / width) * 2.0 - 1.0
        ny = 1.0 - (float(y) / height) * 2.0

        near = np.array([nx, ny, -1.0, 1.0], dtype=np.float32)
        far = np.array([nx, ny, 1.0, 1.0], dtype=np.float32)
        w_near = inv @ near
        w_far = inv @ far
        if abs(float(w_near[3])) < 1e-6 or abs(float(w_far[3])) < 1e-6:
            return None

        p0 = w_near[:3] / w_near[3]
        p1 = w_far[:3] / w_far[3]
        d = p1 - p0

        eye = self.camera.eye()
        plane_p = self.camera.target
        n = plane_p - eye
        nn = float(np.linalg.norm(n))
        if nn <= 1e-6:
            return None
        n = n / nn

        denom = float(np.dot(n, d))
        if abs(denom) < 1e-6:
            return None
        t = float(np.dot(n, (plane_p - p0)) / denom)
        p = p0 + d * t
        return torch.tensor(p, device=self.sim.device, dtype=torch.float32)
