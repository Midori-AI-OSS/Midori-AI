from __future__ import annotations

import numpy as np
import torch

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from point_cloud_weave.colors import hsv_to_rgb


@dataclass(frozen=True)
class TargetPointCloud:
    targets: torch.Tensor
    colors: torch.Tensor
    intensity: torch.Tensor
    activation_time: torch.Tensor


def _compute_weights(rgb_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rgb = rgb_u8.astype(np.float32) / 255.0
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    weights = np.clip(luma - 0.02, 0.0, 1.0) ** 2.2

    greenish = (g > 0.12) & (g >= r * 1.05) & (g >= b * 1.05)
    hair_weights = weights * greenish.astype(np.float32)
    body_weights = weights * (~greenish).astype(np.float32)

    return hair_weights, body_weights


def sample_reference_image_targets(
    *,
    image_path: Path,
    n_points: int,
    ambient_ratio: float,
    seed: int,
    device: torch.device,
    world_scale: float = 1.0,
    depth_noise: float = 0.12,
    spawn_group_size: int = 4096,
    spawn_delay_s: float = 0.010,
) -> TargetPointCloud:
    img = Image.open(image_path).convert("RGB")
    rgb = np.asarray(img, dtype=np.uint8)
    height, width, _ = rgb.shape

    hair_w, body_w = _compute_weights(rgb)
    w_total = float(hair_w.sum() + body_w.sum())
    if w_total <= 0.0:
        raise ValueError(f"No non-black pixels found in {image_path}")

    hair_ratio = float(hair_w.sum()) / w_total
    hair_ratio = float(min(0.65, max(0.10, hair_ratio * 1.55)))
    hair_points = max(1, int(round(n_points * hair_ratio)))
    body_points = max(1, n_points - hair_points)

    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)

    hair_weights = torch.from_numpy(hair_w.reshape(-1)).to(torch.float32)
    body_weights = torch.from_numpy(body_w.reshape(-1)).to(torch.float32)

    hair_idx = torch.multinomial(hair_weights, hair_points, replacement=True, generator=gen)
    body_idx = torch.multinomial(body_weights, body_points, replacement=True, generator=gen)
    idx = torch.cat((hair_idx, body_idx), dim=0)

    xy = torch.stack((idx % width, idx // width), dim=-1).to(torch.float32)
    x = (xy[:, 0] / (width - 1.0) - 0.5) * 2.0
    y = (0.5 - xy[:, 1] / (height - 1.0)) * 2.0
    aspect = width / height
    x = x * aspect

    cpu_targets = torch.empty((n_points, 3), dtype=torch.float32)
    cpu_targets[:, 0] = x * world_scale
    cpu_targets[:, 1] = y * world_scale
    cpu_targets[:, 2] = torch.randn((n_points,), generator=gen) * depth_noise * world_scale

    perm = torch.randperm(n_points, generator=gen)
    cpu_targets = cpu_targets[perm]

    activation_time = (torch.arange(n_points, dtype=torch.int64)[perm] // int(spawn_group_size)).to(torch.float32)
    activation_time = activation_time * float(spawn_delay_s)

    is_hair = torch.zeros((n_points,), dtype=torch.bool)
    is_hair[:hair_points] = True
    is_hair = is_hair[perm]

    hair_hue = torch.normal(mean=0.33, std=0.02, size=(n_points,), generator=gen)
    hair_sat = torch.normal(mean=0.92, std=0.06, size=(n_points,), generator=gen)
    hair_val = torch.normal(mean=0.86, std=0.06, size=(n_points,), generator=gen)
    hair_hsv = torch.stack((hair_hue, hair_sat, hair_val), dim=-1)
    hair_rgb = hsv_to_rgb(hair_hsv)

    gold_hue = torch.normal(mean=0.12, std=0.03, size=(n_points,), generator=gen)
    gold_sat = torch.normal(mean=0.68, std=0.10, size=(n_points,), generator=gen)
    gold_val = torch.normal(mean=0.92, std=0.06, size=(n_points,), generator=gen)
    gold_hsv = torch.stack((gold_hue, gold_sat, gold_val), dim=-1)
    gold_rgb = hsv_to_rgb(gold_hsv)

    colors = torch.where(is_hair[:, None], hair_rgb, gold_rgb).clamp(0.0, 1.0)

    base_intensity = torch.normal(mean=1.0, std=0.25, size=(n_points,), generator=gen).clamp(0.2, 2.5)
    intensity = torch.where(is_hair, base_intensity * 0.85, base_intensity * 1.0)

    ambient_ratio = float(max(0.0, ambient_ratio))
    ambient_points = int(round(n_points * ambient_ratio))
    if ambient_points <= 0:
        return TargetPointCloud(
            targets=cpu_targets.to(device, non_blocking=True),
            colors=colors.to(device, non_blocking=True),
            intensity=intensity.to(device, non_blocking=True),
            activation_time=activation_time.to(device, non_blocking=True),
        )

    ambient_scale_xy = 4.4 * world_scale
    ambient_scale_z = 2.4 * world_scale
    ambient = torch.empty((ambient_points, 3), dtype=torch.float32)
    ambient[:, 0] = (torch.rand((ambient_points,), generator=gen) * 2.0 - 1.0) * ambient_scale_xy
    ambient[:, 1] = (torch.rand((ambient_points,), generator=gen) * 2.0 - 1.0) * ambient_scale_xy
    ambient[:, 2] = (torch.rand((ambient_points,), generator=gen) * 2.0 - 1.0) * ambient_scale_z

    ambient_gold_hue = torch.normal(mean=0.12, std=0.05, size=(ambient_points,), generator=gen)
    ambient_gold_sat = torch.normal(mean=0.55, std=0.18, size=(ambient_points,), generator=gen)
    ambient_gold_val = torch.normal(mean=0.55, std=0.25, size=(ambient_points,), generator=gen)
    ambient_hsv = torch.stack((ambient_gold_hue, ambient_gold_sat, ambient_gold_val), dim=-1)
    ambient_rgb = hsv_to_rgb(ambient_hsv).clamp(0.0, 1.0)
    ambient_intensity = torch.normal(mean=0.32, std=0.18, size=(ambient_points,), generator=gen).clamp(0.05, 0.75)
    ambient_activation = torch.full((ambient_points,), -10.0, dtype=torch.float32)

    all_targets = torch.cat((cpu_targets, ambient), dim=0)
    all_colors = torch.cat((colors, ambient_rgb), dim=0)
    all_intensity = torch.cat((intensity, ambient_intensity), dim=0)
    all_activation = torch.cat((activation_time, ambient_activation), dim=0)

    return TargetPointCloud(
        targets=all_targets.to(device, non_blocking=True),
        colors=all_colors.to(device, non_blocking=True),
        intensity=all_intensity.to(device, non_blocking=True),
        activation_time=all_activation.to(device, non_blocking=True),
    )
