"""Zorluk puanlama: mantık çözücüsünün ihtiyaç duyduğu en gelişmiş teknik (SPEC §5).

Kademeler (ölçümle ayarlandı, bkz. tests/ ve README notları):
    kolay    en fazla 3. seviye (çift, boşluk, sayma)
    orta     4. seviye gerekir (satır analizi / = × zinciri)
    zor      5. seviye gerekir, 1 kez varsayım-çelişki
    çok zor  5. seviye gerekir, en az HARDEST_MIN_CONTRADICTIONS kez varsayım-çelişki
"""
from __future__ import annotations

from dataclasses import dataclass

from .rules import N
from .solver import solve

TIERS = ("kolay", "orta", "zor", "çok zor")
# Üretimde ipucu çıkarırken izin verilen en yüksek teknik seviyesi.
TIER_MAX_LEVEL = {"kolay": 3, "orta": 4, "zor": 5, "çok zor": 5}
HARDEST_MIN_CONTRADICTIONS = 2
# Pazartesi (0) ... Pazar (6). Ayarlanabilir (SPEC §5).
WEEKDAY_TIERS = ("kolay", "kolay", "orta", "orta", "zor", "zor", "çok zor")


@dataclass(frozen=True)
class Rating:
    solved: bool
    max_level: int
    contradictions: int
    technique_counts: tuple  # ((teknik, adet), ...) sıralı
    tier: str | None

    @property
    def score(self) -> int:
        """Kaba sayısal zorluk: önce seviye, sonra varsayım sayısı."""
        return self.max_level * 10 + self.contradictions


def tier_of(max_level: int, contradictions: int) -> str:
    if max_level <= 3:
        return "kolay"
    if max_level == 4:
        return "orta"
    if contradictions >= HARDEST_MIN_CONTRADICTIONS:
        return "çok zor"
    return "zor"


def rate(givens: dict, links: dict, n: int = N) -> Rating:
    res = solve(givens, links, n=n)
    counts = res.technique_counts()
    contradictions = counts.get("contradiction", 0)
    tier = tier_of(res.max_level, contradictions) if res.solved else None
    return Rating(res.solved, res.max_level, contradictions, tuple(sorted(counts.items())), tier)
