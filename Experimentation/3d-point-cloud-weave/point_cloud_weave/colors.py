from __future__ import annotations

import torch


def hsv_to_rgb(hsv: torch.Tensor) -> torch.Tensor:
    h = hsv[..., 0] % 1.0
    s = torch.clamp(hsv[..., 1], 0.0, 1.0)
    v = torch.clamp(hsv[..., 2], 0.0, 1.0)

    i = torch.floor(h * 6.0).to(torch.int64)
    f = h * 6.0 - i.to(h.dtype)

    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    i = i % 6
    r = torch.where(i == 0, v, torch.where(i == 1, q, torch.where(i == 2, p, torch.where(i == 3, p, torch.where(i == 4, t, v)))))
    g = torch.where(i == 0, t, torch.where(i == 1, v, torch.where(i == 2, v, torch.where(i == 3, q, torch.where(i == 4, p, p)))))
    b = torch.where(i == 0, p, torch.where(i == 1, p, torch.where(i == 2, t, torch.where(i == 3, v, torch.where(i == 4, v, q)))))

    return torch.stack((r, g, b), dim=-1)

