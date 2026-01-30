from __future__ import annotations

import math

import torch

from pathlib import Path

from point_cloud_game.sim import WeaveSim
from point_cloud_game.targets import sample_reference_image_targets


class PointCloudManager:
    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = torch.device(device)
        self.sim: WeaveSim | None = None
        self.total_points = 250_000 # Target total count
        
        self.weave_indices: tuple[int, int] | None = None
        self.projectile_indices: list[int] = []
        self.aspect_ratio = 9/16
        self._free_foe_ranges: list[tuple[int, int]] = []

    def initialize_sim(self, weave_image_path: str, *, player_anchor: tuple[float, float, float] = (0.0, -1.2, 0.0)):
        # Use high-quality sampling from targets.py
        # We reserve points for Weave + Ambient first
        # We want Weave to be ~60k points? 
        # The total points in sim includes Foes/Projectiles.
        # sample_reference_image_targets returns a FIXED set.
        # We need to adapt it to be part of a larger buffer OR use it as the base.
        
        # Let's target Weave = 50k points
        weave_pts = 60_000
        
        cloud = sample_reference_image_targets(
            image_path=Path(weave_image_path),
            n_points=weave_pts,
            ambient_ratio=0.1, # Small ambient for background
            seed=42,
            device=self.device,
            world_scale=0.35,
            depth_noise=0.12, # Match original app depth
            spawn_group_size=4096,
            spawn_delay_s=0.01
        )
        
        # Weave Target Positions
        weave_targets = cloud.targets

        # Center the player character at bottom-middle.
        center = weave_targets.mean(dim=0)
        desired = torch.tensor(player_anchor, device=self.device, dtype=weave_targets.dtype)
        weave_targets = (weave_targets - center) + desired
        
        num_weave_ambient = weave_targets.shape[0]
        self.weave_indices = (0, num_weave_ambient)
        
        # Now we need to fill the Rest of the buffer (Total - Weave) with "Empty" / "Foes".
        remaining = self.total_points - num_weave_ambient
        if remaining < 0:
            raise ValueError(f"Total points {self.total_points} too small for Weave {num_weave_ambient}")
            
        # Create full buffers
        # 1. Targets
        # Initialize remaining targets far away
        empty_targets = torch.randn((remaining, 3), device=self.device) * 100.0
        all_targets = torch.cat([weave_targets, empty_targets], dim=0)

        # 2. Colors
        # Weave colors are Gold/Green from sampling
        # Foes? Let's make foes Red by default or White.
        # Initialize remaining as Red for visual debugging if they appear? Or White.
        empty_colors = torch.ones((remaining, 3), device=self.device)
        # Make them faint red
        empty_colors[:] = torch.tensor([1.0, 0.5, 0.5], device=self.device)
        all_colors = torch.cat([cloud.colors, empty_colors], dim=0)
        
        # 3. Intensity
        empty_intensity = torch.ones(remaining, device=self.device)
        all_intensity = torch.cat([cloud.intensity, empty_intensity], dim=0)
        
        # 4. Activation
        # Weave: from cloud (fade in logic) OR force instant
        # User wants instant? 
        # cloud.activation_time has stagger.
        # Let's keep stagger for "Cool spawn" effect? 
        # User complained about blank screen. 
        # Let's force instant for now to be safe, or start time at 10.0.
        # Actually, let's allow stagger but ensure we simulate enough or offset time.
        # Better: Force instant for Weave.
        instant_weave = torch.full((num_weave_ambient,), -5.0, device=self.device)
        instant_empty = torch.full((remaining,), -5.0, device=self.device)
        all_activation = torch.cat([instant_weave, instant_empty], dim=0)
        
        self.sim = WeaveSim(
            targets=all_targets,
            colors=all_colors,
            intensity=all_intensity,
            activation_time=all_activation,
            seed=42
        )
        
        self.free_start = num_weave_ambient
        self.projectile_start = self.total_points - 50000 
        self._dynamic_start = int(self.free_start)
        self._proj_ptr = int(self.projectile_start)
        
    def allocate_foe(self, num_points: int) -> tuple[int, int] | None:
        for i, (start, end) in enumerate(self._free_foe_ranges):
            span = end - start
            if span < num_points:
                continue
            if span == num_points:
                self._free_foe_ranges.pop(i)
                return (start, end)
            out = (start, start + num_points)
            self._free_foe_ranges[i] = (start + num_points, end)
            return out

        start = self.free_start
        end = start + num_points
        if end > self.projectile_start:
            return None # Out of points
        
        self.free_start = end
        return (start, end)
    
    def free_foe(self, range_indices: tuple[int, int]) -> None:
        self._free_foe_ranges.append(range_indices)

    def allocate_beam(self, num_points: int) -> tuple[int, int]:
        # Simple allocator in reserved projectile space
        # [self.projectile_start ... self.total_points]
        # Use a "current_projectile_ptr"
        
        start = self._proj_ptr
        end = start + num_points
        
        if end >= self.total_points:
            # Wrap around? Or Reset?
            # Ring buffer logic needed if we want to live long.
            # Simple wrap:
            start = self.projectile_start
            end = start + num_points
            
        self._proj_ptr = end
        return (start, end)

    def update_targets(self, targets_update: dict[tuple[int, int], torch.Tensor]):
        """
        updates: dict where key is (start, end) index tuple, value is New Target Positions (Nx3)
        """
        for (start, end), new_pos in targets_update.items():
            # Ensure shape matches
            count = end - start
            if new_pos.shape[0] != count:
                # Resample or trim?
                continue
            
            self.sim.targets[start:end] = new_pos

    def reset_dynamic_allocators(self) -> None:
        self._free_foe_ranges.clear()
        self.free_start = int(self._dynamic_start)
        self._proj_ptr = int(self.projectile_start)

    def generate_shape(self, shape_type: str, num_points: int) -> torch.Tensor:
        if shape_type == 'square':
            # random in [-1, 1] cube
            pts = torch.rand((num_points, 3), device=self.device) * 2.0 - 1.0
            pts[:, 2] = 0 # flatten
            return pts
        elif shape_type == 'circle':
            # rejection or polar
            r = torch.sqrt(torch.rand(num_points, device=self.device))
            theta = torch.rand(num_points, device=self.device) * 2 * math.pi
            pts = torch.zeros((num_points, 3), device=self.device)
            pts[:, 0] = r * torch.cos(theta)
            pts[:, 1] = r * torch.sin(theta)
            return pts
            
        return torch.randn((num_points, 3), device=self.device)
