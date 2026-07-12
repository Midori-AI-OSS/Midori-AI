from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StudioConfig:
    music_root: Path = Path.home() / "Music" / "MidoriAI"
    downloads_dir: Path = Path.home() / "Downloads"
    opencode_model: str = "lm-studio/qwen/qwen3.6-27b"
    opencode_variant: str = "xhigh"
    opencode_fallback_model: str = "deepseek/deepseek-v4-flash"
    opencode_fallback_variant: str = "max"
    essentia_backend: str = "uv"
    essentia_uv_workdir: Path = Path("/tmp/luna-essentia-uv")
    essentia_uv_cache_dir: Path = Path("/tmp/luna-essentia-uv-cache")
    essentia_uv_package_spec: str = "essentia"
    max_opencode_attempts: int = 3
    vibe_cache_max_age_seconds: int = 365 * 24 * 60 * 60
    related_comment_reference_limit: int = 30
    related_comment_max_length: int = 220
    related_vibe_retries: int = 2
    vibe_worker_count: int = 0  # 0 = auto (nproc/2)
    prompts_path: Path = Path("prompts.toml")
    prompts_base_path: Path = Path("prompts.base.toml")
    feedback_queue_path: Path = Path(
        "/tmp/midoriai/radiostation-manager/feedback_queue.json"
    )
    prompts_for_refinement_model: str = "deepseek/deepseek-v4-flash"
    prompts_for_refinement_variant: str = "max"

    @classmethod
    def load(cls, path: Path | None = None) -> StudioConfig:
        cfg = cls()
        search_paths = [
            path,
            Path("config.toml"),
            Path.home() / ".config" / "luna-studio" / "config.toml",
        ]
        import os

        music_root_env = os.environ.get("LUNA_MUSIC_ROOT", "")
        if music_root_env:
            cfg.music_root = Path(music_root_env)

        for p in search_paths:
            if p and p.exists():
                data = tomllib.loads(p.read_text())
                for key, val in data.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, val)
                break
        return cfg


def get_config() -> StudioConfig:
    return StudioConfig.load()
