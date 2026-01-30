from __future__ import annotations

import torch

from dataclasses import dataclass


@dataclass
class SimParams:
    speed_gain: float = 1.8
    speed_cap: float = 2.2
    accel: float = 12.0
    damping: float = 2.2
    activation_fade_s: float = 0.75
    swirl_strength: float = 0.12
    noise_strength: float = 0.02

    disrupt_strength: float = 0.55
    disrupt_prob: float = 0.08
    disrupt_radius: float = 1.3
    repel_strength: float = 3.0
    repel_radius: float = 0.75
    repel_sigma: float = 0.42


class WeaveSim:
    def __init__(
        self,
        *,
        targets: torch.Tensor,
        colors: torch.Tensor,
        intensity: torch.Tensor,
        activation_time: torch.Tensor,
        seed: int,
    ) -> None:
        self.device = targets.device
        self.targets = targets
        self.colors = colors
        self.intensity = intensity
        self.activation_time = activation_time

        self.params = SimParams()
        self.paused = False

        self._rng = torch.Generator(device=self.device)
        self._rng.manual_seed(seed)
        self.reset_state(seed=seed)

    @property
    def n_points(self) -> int:
        return int(self.pos.shape[0])

    def reset_state(self, *, seed: int) -> None:
        self.time_s = 0.0
        self.paused = False

        gen = torch.Generator(device="cpu")
        gen.manual_seed(int(seed) ^ 0x5F3759DF)
        cpu = torch.empty_like(self.targets, device="cpu")
        cpu.uniform_(-3.0, 3.0, generator=gen)
        self.pos = cpu.to(self.device, non_blocking=True)
        self.vel = torch.zeros_like(self.pos)

    def step(self, dt_s: float) -> None:
        if self.paused:
            return

        t = float(self.time_s)
        self.time_s = t + float(dt_s)

        targets = self.targets
        pos = self.pos
        vel = self.vel

        delta = targets - pos
        dist = torch.linalg.vector_norm(delta, dim=-1).clamp_min(1e-6)
        desired_dir = delta / dist[:, None]
        speed = torch.clamp(dist * float(self.params.speed_gain), 0.0, float(self.params.speed_cap))
        desired_vel = desired_dir * speed[:, None]

        a0 = self.activation_time
        fade = float(self.params.activation_fade_s)
        active = torch.clamp((torch.as_tensor(self.time_s, device=self.device) - a0) / max(1e-6, fade), 0.0, 1.0)

        accel = float(self.params.accel)
        vel = vel + (desired_vel - vel) * (accel * float(dt_s)) * active[:, None]

        damping = torch.exp(torch.as_tensor(-float(self.params.damping) * float(dt_s), device=self.device))
        vel = vel * damping

        swirl = float(self.params.swirl_strength)
        if swirl > 0.0:
            up = torch.tensor([0.0, 1.0, 0.0], device=self.device)
            vel = vel + torch.cross(pos, up.expand_as(pos), dim=-1) * (swirl * float(dt_s))

        noise = float(self.params.noise_strength)
        if noise > 0.0:
            vel = vel + torch.randn_like(pos, generator=self._rng) * (noise * float(dt_s)) * (1.0 - active)[:, None]

        pos = pos + vel * float(dt_s)

        self.pos = pos
        self.vel = vel

    def apply_disruption(self, *, center: torch.Tensor, strength: float) -> None:
        if strength <= 0.0 or self.params.disrupt_prob <= 0.0:
            return

        d = self.pos - center[None, :]
        dist = torch.linalg.vector_norm(d, dim=-1)

        radius = float(self.params.disrupt_radius)
        in_range = dist < radius
        if not bool(in_range.any()):
            return

        prob = float(self.params.disrupt_prob) * float(strength)
        prob = max(0.0, min(0.6, prob))
        mask = (torch.rand((self.n_points,), device=self.device, generator=self._rng) < prob) & in_range
        if not bool(mask.any()):
            return

        direction = d / dist.clamp_min(1e-6)[:, None]
        jitter = torch.randn_like(self.pos, generator=self._rng)
        impulse = direction * float(self.params.disrupt_strength) + jitter * 0.25
        self.vel = self.vel + impulse * mask[:, None]

    def apply_repulsion(self, *, center: torch.Tensor, strength: float) -> None:
        if strength <= 0.0 or self.params.repel_strength <= 0.0:
            return

        d = self.pos - center[None, :]
        dist = torch.linalg.vector_norm(d, dim=-1)

        radius = float(self.params.repel_radius)
        in_range = dist < radius
        if not bool(in_range.any()):
            return

        sigma = float(max(1e-3, self.params.repel_sigma))
        w = torch.exp(-(dist * dist) / (2.0 * sigma * sigma)) * in_range.to(dist.dtype)
        direction = d / dist.clamp_min(1e-6)[:, None]
        impulse = direction * (float(self.params.repel_strength) * float(strength)) * w[:, None]
        self.vel = self.vel + impulse
