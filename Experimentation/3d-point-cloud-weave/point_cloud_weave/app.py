from __future__ import annotations

import getpass
import os

import torch

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from point_cloud_weave.profile import ProfilerController
from point_cloud_weave.sim import WeaveSim
from point_cloud_weave.style import app_stylesheet
from point_cloud_weave.targets import sample_reference_image_targets
from point_cloud_weave.ui import AppPaths
from point_cloud_weave.ui import MainWindow


@dataclass(frozen=True)
class AppArgs:
    points: int
    ambient_ratio: float
    seed: int
    device: str
    image: Path
    spawn_group_size: int
    spawn_delay_s: float
    profile_seconds: float | None


def run_app(args: AppArgs) -> int:
    if not os.environ.get("DISPLAY") and Path("/tmp/.X11-unix/X1").exists():
        os.environ["DISPLAY"] = ":1"
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/tmp/xdg-{getpass.getuser()}")
    Path(os.environ["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)

    torch.set_float32_matmul_precision("high")

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available; use --device cpu or --device auto.")
        device = torch.device(args.device)

    cloud = sample_reference_image_targets(
        image_path=args.image,
        n_points=int(args.points),
        ambient_ratio=float(args.ambient_ratio),
        seed=int(args.seed),
        device=device,
        spawn_group_size=int(args.spawn_group_size),
        spawn_delay_s=float(args.spawn_delay_s),
    )

    sim = WeaveSim(
        targets=cloud.targets,
        colors=cloud.colors,
        intensity=cloud.intensity,
        activation_time=cloud.activation_time,
        seed=int(args.seed),
    )

    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(0)
    fmt.setStencilBufferSize(0)
    fmt.setSamples(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication([])
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app.setStyleSheet(app_stylesheet())

    profiler = ProfilerController()
    if args.profile_seconds is not None and args.profile_seconds > 0:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        profiler.start(seconds=float(args.profile_seconds), out_path=Path("profiles") / f"startup-{ts}.pstats")

    win = MainWindow(sim=sim, profiler=profiler, paths=AppPaths(render_dir=Path("renders"), profile_dir=Path("profiles")))
    win.show()
    return app.exec()
