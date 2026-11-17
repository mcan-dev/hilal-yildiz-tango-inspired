"""Hilal ve yıldız çokgenleri. Font glifine bağımlı değil, saf geometri.

Hilal oranları Türk bayrağından: iç daire yarıçapı dış dairenin 0,8 katı,
merkezler arası uzaklık dış yarıçapın 0,25 katı (açıklık sağa).
"""
from __future__ import annotations

import math


def crescent_points(cx: float, cy: float, R: float, steps: int = 40) -> list[float]:
    r = 0.8 * R
    d = 0.25 * R
    # Görsel ağırlığı ortalamak için hilali biraz sağa kaydır.
    cx += 0.12 * R
    # İki dairenin kesişimi (dış daire merkezi orijinde, iç daire (d, 0)'da)
    x = (R * R - r * r + d * d) / (2 * d)
    y = math.sqrt(max(R * R - x * x, 0.0))
    t0 = math.atan2(y, x)          # dış yay: t0 -> 2π - t0 (sol taraftan)
    p0 = math.atan2(y, x - d)      # iç yay: 2π - p0 -> p0 (geri dönüş)
    pts: list[float] = []
    for i in range(steps + 1):
        t = t0 + (2 * math.pi - 2 * t0) * i / steps
        pts += [cx + R * math.cos(t), cy - R * math.sin(t)]
    for i in range(steps + 1):
        p = (2 * math.pi - p0) - (2 * math.pi - 2 * p0) * i / steps
        pts += [cx + d + r * math.cos(p), cy - r * math.sin(p)]
    return pts


def star_points(cx: float, cy: float, R: float, inner_ratio: float = 0.40,
                rotation: float = -math.pi / 2) -> list[float]:
    """Beş köşeli yıldız. `rotation`: ilk köşenin açısı (varsayılan: yukarı)."""
    pts: list[float] = []
    for i in range(10):
        rad = R if i % 2 == 0 else R * inner_ratio
        a = rotation + i * math.pi / 5
        pts += [cx + rad * math.cos(a), cy + rad * math.sin(a)]
    return pts
