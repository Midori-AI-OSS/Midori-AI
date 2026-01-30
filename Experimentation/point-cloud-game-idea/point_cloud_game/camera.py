from __future__ import annotations

import numpy as np

from dataclasses import dataclass
from dataclasses import field
from math import cos
from math import sin


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n <= 1e-9:
        return v
    return v / n


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    f = _normalize(target - eye)
    r = _normalize(np.cross(f, up))
    u = np.cross(r, f)

    m = np.eye(4, dtype=np.float32)
    m[0, :3] = r
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -float(np.dot(r, eye))
    m[1, 3] = -float(np.dot(u, eye))
    m[2, 3] = float(np.dot(f, eye))
    return m


def perspective(fovy_rad: float, aspect: float, z_near: float, z_far: float) -> np.ndarray:
    f = 1.0 / float(np.tan(fovy_rad / 2.0))
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / float(aspect)
    m[1, 1] = f
    m[2, 2] = (z_far + z_near) / (z_near - z_far)
    m[2, 3] = (2.0 * z_far * z_near) / (z_near - z_far)
    m[3, 2] = -1.0
    return m


@dataclass
class TopDownCamera:
    target: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0], dtype=np.float32))
    # Fixed position matching OrbitCamera defaults (pitch=0.2, dist=3.2)
    # y = 3.2 * sin(0.2) ~= 0.635
    # z = 3.2 * cos(0.2) ~= 3.136
    eye_pos: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.635, 3.136], dtype=np.float32))
    up: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0, 0.0], dtype=np.float32))
    fovy_rad: float = 0.70
    z_near: float = 0.05
    z_far: float = 80.0
    
    # Ignored legacy fields to avoid breakage if referenced elsewhere (though we control usage)
    yaw: float = 0.0 
    pitch: float = 0.0
    distance: float = 3.8

    def eye(self) -> np.ndarray:
        return self.eye_pos

    def view_matrix(self) -> np.ndarray:
        return look_at(self.eye_pos, self.target, self.up)

    def proj_matrix(self, aspect: float) -> np.ndarray:
        return perspective(self.fovy_rad, aspect, self.z_near, self.z_far)
