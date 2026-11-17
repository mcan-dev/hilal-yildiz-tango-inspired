"""Tohumlu bulmaca üreteci (SPEC §4).

1. Tohumdan bir geçerli çözüm ızgarası seçilir.
2. Başlangıçta tüm hücreler sabit, tüm komşu çiftlere işaret verilmiş kabul edilir.
3. İpuçları tohumlu rastgele sırayla çıkarılır. Çıkarınca (a) hâlâ tek çözüm varsa
   ve (b) mantık çözücüsü hedef seviyeyi aşmadan tahminsiz çözebiliyorsa çıkarma
   kalıcı olur, aksi halde ipucu geri konur. Sonuç minimal bir ipucu kümesidir.
4. Kalite filtreleri ve hedef zorluk tutmazsa aynı tohumun bir sonraki alt dizisi
   ("<tohum>:<deneme>") denenir. Böylece sonuç tamamen tohuma bağlı kalır.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .difficulty import TIER_MAX_LEVEL, TIERS, Rating, rate
from .rules import DIFF, N, SAME, UNIQUE_LINES, geometry
from .solver import board_from_givens, count_solutions, logic_solvable, next_move


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class QualityConfig:
    """Kalite filtreleri (SPEC §4.6). Her biri ayrı ayrı ayarlanabilir."""
    # Dağılım: tahta 4 adet 3x3 çeyreğe bölünür. Her çeyrekte en az bu kadar ipucu,
    # tek bir çeyrekte ipuçlarının en fazla bu oranı bulunabilir.
    min_clues_per_quadrant: int = 1
    max_quadrant_share: float = 0.5
    # İlk hamle: başlangıç tahtasında bu seviyeye kadarki bir teknikle doğrudan
    # çıkarılabilen en az bir hücre olmalı.
    first_move_max_level: int = 3
    # Karışım: en az bu kadar sabit sembol ve en az bu kadar işaret.
    min_givens: int = 2
    min_links: int = 2


DEFAULT_QUALITY = QualityConfig()


@dataclass(frozen=True)
class Puzzle:
    solution: tuple
    givens: dict
    links: dict
    seed: object
    attempt: int
    level: int            # üretimde izin verilen en yüksek teknik seviyesi
    rating: Rating
    target_tier: str
    notes: tuple = field(default=())
    n: int = N

    @property
    def tier(self) -> str | None:
        return self.rating.tier

    @property
    def clue_count(self) -> int:
        return len(self.givens) + len(self.links)

    @property
    def fingerprint(self) -> tuple:
        return (tuple(sorted(self.givens.items())), tuple(sorted(self.links.items())))

    def to_dict(self) -> dict:
        """JSON'a yazılabilir biçim (önbellek için)."""
        return {
            "solution": [list(r) for r in self.solution],
            "givens": [[r, c, v] for (r, c), v in sorted(self.givens.items())],
            "links": [[a[0], a[1], b[0], b[1], t] for (a, b), t in sorted(self.links.items())],
            "seed": str(self.seed),
            "attempt": self.attempt,
            "level": self.level,
            "target_tier": self.target_tier,
            "notes": list(self.notes),
            "n": self.n,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        givens = {(r, c): v for r, c, v in data["givens"]}
        links = {((r1, c1), (r2, c2)): t for r1, c1, r2, c2, t in data["links"]}
        n = data.get("n", len(data["solution"]))
        return cls(tuple(tuple(r) for r in data["solution"]), givens, links, data["seed"],
                   data["attempt"], data["level"], rate(givens, links, n), data["target_tier"],
                   tuple(data.get("notes", ())), n)


def _full_clues(sol) -> tuple[dict, dict]:
    n = len(sol)
    cells, _, edges = geometry(n)
    givens = {cell: sol[cell[0]][cell[1]] for cell in cells}
    links = {
        (a, b): SAME if sol[a[0]][a[1]] == sol[b[0]][b[1]] else DIFF
        for a, b in edges
    }
    return givens, links


def _still_good(givens: dict, links: dict, level: int, unique_lines: bool,
                n: int = N) -> bool:
    # Tamamıyla çözen zorunlu çıkarımlar sabit bir ızgara bıraktığı için teklik sağlar.
    return logic_solvable(givens, links, level, n=n)


def reduce_clues(rng: random.Random, level: int, unique_lines: bool | None = None,
                 n: int = N, db_path=None, con=None):
    """Bir çözüm seçip ipuçlarını minimal kümeye indirir. Döner: (çözüm, givens, links)."""
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    from .db import connect, pick_solution
    own_connection = con is None
    if own_connection:
        con = connect(db_path)
    try:
        sol = pick_solution(con, n, rng.getrandbits(64))
    finally:
        if own_connection:
            con.close()
    givens, links = _full_clues(sol)
    items = [("g", k) for k in sorted(givens)] + [("l", k) for k in sorted(links)]
    rng.shuffle(items)
    for kind, key in items:
        g2, l2 = dict(givens), dict(links)
        (g2 if kind == "g" else l2).pop(key)
        if _still_good(g2, l2, level, unique_lines, n):
            givens, links = g2, l2
    return sol, givens, links


def _quadrant(cell, n: int = N) -> int:
    half = n // 2
    return (cell[0] >= half) * 2 + (cell[1] >= half)


def quality_issues(givens: dict, links: dict, cfg: QualityConfig = DEFAULT_QUALITY,
                   n: int = N) -> list[str]:
    """Kalite filtrelerinden geçemeyen maddelerin listesi (boşsa bulmaca uygun)."""
    issues = []
    total = len(givens) + len(links)
    per_q = [0, 0, 0, 0]
    for cell in givens:
        per_q[_quadrant(cell, n)] += 1
    for a, b in links:
        for q in {_quadrant(a, n), _quadrant(b, n)}:
            per_q[q] += 1
    if min(per_q) < cfg.min_clues_per_quadrant:
        issues.append(f"dağılım: boş çeyrek var {per_q}")
    if total and max(per_q) > cfg.max_quadrant_share * total:
        issues.append(f"dağılım: ipuçları tek çeyrekte yığılmış {per_q}")
    if next_move(board_from_givens(givens, n), links, cfg.first_move_max_level) is None:
        issues.append("ilk hamle görünmüyor")
    if len(givens) < cfg.min_givens:
        issues.append(f"karışım: az sabit sembol ({len(givens)})")
    if len(links) < cfg.min_links:
        issues.append(f"karışım: az işaret ({len(links)})")
    return issues


def generate(seed, tier: str = "orta", exclude=frozenset(), max_attempts: int = 150,
             quality: QualityConfig = DEFAULT_QUALITY,
             unique_lines: bool | None = None, accept=None, n: int = N,
             db_path=None) -> Puzzle:
    """Tohumdan hedef zorlukta, minimal ve kalite filtreli bir bulmaca üretir.

    `exclude`: daha önce verilmiş bulmacaların parmak izleri (tekrar önleme).
    `accept`: verilirse bu kümedeki herhangi bir zorluk kabul edilir (örneğin
    "en az orta"); `tier` yalnızca hiçbiri tutmazsa yaklaşılacak hedeftir.
    Hedef zorluk `max_attempts` denemede tutmazsa filtrelerden geçen en yakın
    zorluktaki bulmaca döner (notes alanında belirtilir).
    """
    geometry(n)
    accept = frozenset(accept) if accept else frozenset({tier})
    if tier not in TIERS or not accept <= set(TIERS):
        raise ValueError(f"bilinmeyen zorluk: {tier!r} / {sorted(accept)}")
    level = max(TIER_MAX_LEVEL[t] for t in accept | {tier})
    best: Puzzle | None = None
    from .db import connect
    con = connect(db_path)
    try:
        for attempt in range(max_attempts):
            rng = random.Random(f"{seed}:{attempt}")
            sol, givens, links = reduce_clues(rng, level, unique_lines, n, con=con)
            if quality_issues(givens, links, quality, n):
                continue
            puzzle = Puzzle(sol, givens, links, seed, attempt, level,
                            rate(givens, links, n), tier, n=n)
            if puzzle.fingerprint in exclude:
                continue
            if puzzle.tier in accept:
                return puzzle
            if best is None or _tier_gap(puzzle, tier) < _tier_gap(best, tier):
                best = puzzle
        if best is None:
            raise GenerationError(f"{seed!r} tohumu için {max_attempts} denemede uygun bulmaca yok")
        return Puzzle(best.solution, best.givens, best.links, best.seed, best.attempt, best.level,
                      best.rating, tier, notes=(f"hedef {tier} tutmadı, {best.tier} verildi",), n=n)
    finally:
        con.close()


def _tier_gap(p: Puzzle, tier: str) -> int:
    return abs(TIERS.index(p.tier) - TIERS.index(tier)) if p.tier else 99


def is_minimal(puzzle: Puzzle, unique_lines: bool | None = None) -> bool:
    """Her ipucu gerekli mi? Herhangi biri çıkarılınca bulmaca bozulmalı."""
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    for cell in puzzle.givens:
        g2 = {k: v for k, v in puzzle.givens.items() if k != cell}
        if _still_good(g2, puzzle.links, puzzle.level, unique_lines, puzzle.n):
            return False
    for edge in puzzle.links:
        l2 = {k: v for k, v in puzzle.links.items() if k != edge}
        if _still_good(puzzle.givens, l2, puzzle.level, unique_lines, puzzle.n):
            return False
    return True
