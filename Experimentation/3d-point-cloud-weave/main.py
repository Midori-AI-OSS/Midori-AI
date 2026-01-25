from __future__ import annotations

import argparse
from pathlib import Path

from point_cloud_weave.app import AppArgs
from point_cloud_weave.app import run_app


def main() -> int:
    parser = argparse.ArgumentParser(prog="3d-point-cloud-weave")
    parser.add_argument("--points", type=int, default=180_000)
    parser.add_argument("--ambient-ratio", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--image", type=Path, default=Path("assets/reference.png"))
    parser.add_argument("--spawn-group-size", type=int, default=4096)
    parser.add_argument("--spawn-delay-s", type=float, default=0.010)
    parser.add_argument("--profile-seconds", type=float, default=None)
    args = parser.parse_args()

    return run_app(
        AppArgs(
            points=args.points,
            ambient_ratio=args.ambient_ratio,
            seed=args.seed,
            device=args.device,
            image=args.image,
            spawn_group_size=args.spawn_group_size,
            spawn_delay_s=args.spawn_delay_s,
            profile_seconds=args.profile_seconds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
