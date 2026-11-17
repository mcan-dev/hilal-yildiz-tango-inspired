"""Tarih -> tohum -> bulmaca, ve her açılışta farklı bulmaca için rastgele üretim.

Günlük tohum, tarihin ISO metninin SHA-256 özetinden türetilir. Bu yüzden Python
sürümünden ve makineden bağımsızdır. Zor günlerde üretim birkaç on saniye
sürebildiği için bulmacalar diske yazılıp okunabilir.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from pathlib import Path

from .difficulty import WEEKDAY_TIERS
from .generator import Puzzle, generate
from .rules import N, is_valid_solution, respects_clues
from .solver import count_solutions
from .db import connect, ensure_database, load_puzzle as load_db_puzzle, save_puzzle as save_db_puzzle
from .difficulty import TIER_MAX_LEVEL, rate

SEED_SALT = "hilal-yildiz"
CACHE_VERSION = 1


def seed_for(d: date) -> int:
    digest = hashlib.sha256(f"{SEED_SALT}:{d.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def tier_for(d: date) -> str:
    return WEEKDAY_TIERS[d.weekday()]


def save_puzzle(path: Path, p: Puzzle) -> None:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": CACHE_VERSION, **p.to_dict()}), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def load_puzzle(path: Path) -> Puzzle | None:
    """Diskteki bulmacayı okur ve doğrular. Yoksa ya da bozuksa None döner."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != CACHE_VERSION:
            return None
        p = Puzzle.from_dict(data)
        if (is_valid_solution(p.solution) and respects_clues(p.solution, p.givens, p.links)
                and count_solutions(p.givens, p.links) == 1):
            return p
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def puzzle_for(d: date | None = None, cache_dir: Path | None = None) -> Puzzle:
    """Günün bulmacası. `cache_dir` verilirse önce oradan okunur, yoksa üretilip yazılır."""
    d = d or date.today()
    path = Path(cache_dir) / f"{d.isoformat()}.json" if cache_dir else None
    if path and path.exists():
        p = load_puzzle(path)
        if p is not None and p.seed == str(seed_for(d)):
            return p
    p = generate(seed_for(d), tier_for(d))
    if path:
        save_puzzle(path, p)
    return p


def get_daily_puzzle(d: date, n: int, database_path: Path | None = None) -> Puzzle:
    """Return one deterministic daily puzzle per date and board size from SQLite."""
    if n not in (4, 6, 8):
        raise ValueError("tahta boyutu 4, 6 veya 8 olmalı")
    ensure_database(database_path)
    seed = int(d.strftime("%Y%m%d")) * 100 + n
    con = connect(database_path)
    try:
        cached = load_db_puzzle(con, n, d.isoformat())
        if cached is not None:
            givens, links, solution, _difficulty = cached
            rating = rate(givens, links, n)
            tier = tier_for(d)
            return Puzzle(solution, givens, links, seed, 0,
                          TIER_MAX_LEVEL[tier], rating, tier, n=n)
        p = generate(seed, tier_for(d), n=n, db_path=database_path)
        save_db_puzzle(con, n, d.isoformat(), p.givens, p.links, p.solution,
                       p.rating.score)
        return p
    finally:
        con.close()


def make(seed, n: int = N, tier: str = "orta", database_path: Path | None = None) -> Puzzle:
    """Generate a deterministic puzzle with the requested size and seed."""
    return generate(seed, tier, n=n, db_path=database_path)


# Her açılışta verilecek bulmacaların zorlukları: orta ve zor ("çok zor", yani
# iki ve daha fazla varsayım gerektirenler, oyuncu isteğiyle çıkarıldı).
PLAY_TIERS = ("orta", "zor")


def fingerprint_key(p: Puzzle) -> str:
    return hashlib.sha1(repr(p.fingerprint).encode()).hexdigest()


def random_puzzle(tier: str | None = None, exclude=frozenset()) -> Puzzle:
    """Her çağrıda farklı bir bulmaca (sistem rastgeleliğiyle seçilen tohum).

    `tier` verilmezse PLAY_TIERS içinden ilk tutan kabul edilir (hızlı yol).
    """
    seed = f"rastgele:{random.SystemRandom().getrandbits(64)}"
    if tier is None:
        return generate(seed, "zor", exclude=exclude, accept=PLAY_TIERS)
    return generate(seed, tier, exclude=exclude)


class PuzzlePool:
    """Diskte hazır bekleyen bulmacalar ve daha önce gösterilenlerin geçmişi.

    Zor bulmacaların üretimi uzun sürebildiği için havuz arka planda doldurulur;
    havuz boşsa hızlı yoldan (en az orta) anında bir bulmaca üretilir. Gösterilen
    her bulmaca geçmişe yazılır ve bir daha verilmez.
    """

    def __init__(self, root: Path, size: int = 3, history_limit: int = 1000):
        self.root = Path(root)
        self.dir = self.root / "pool"
        self.history_path = self.root / "history.json"
        self.size = size
        self.history_limit = history_limit
        self._rng = random.SystemRandom()

    # --- geçmiş --------------------------------------------------------
    def history(self) -> list[str]:
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def mark_seen(self, p: Puzzle) -> None:
        hist = [k for k in self.history() if k != fingerprint_key(p)] + [fingerprint_key(p)]
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self.history_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(hist[-self.history_limit:]), encoding="utf-8")
            tmp.replace(self.history_path)
        except OSError:
            pass

    # --- havuz ---------------------------------------------------------
    def files(self) -> list[Path]:
        return sorted(self.dir.glob("*.json")) if self.dir.exists() else []

    def take(self) -> Puzzle | None:
        """Havuzdan rastgele bir bulmaca alır (dosyası silinir). Daha önce görülmüşse atlar."""
        seen = set(self.history())
        files = self.files()
        self._rng.shuffle(files)
        for f in files:
            p = load_puzzle(f)
            try:
                f.unlink()
            except OSError:
                continue  # başka bir süreç almış
            if p is not None and p.target_tier in PLAY_TIERS and fingerprint_key(p) not in seen:
                return p
        return None

    def refill(self) -> int:
        """Havuzu `size` adede tamamlar. Eklenen bulmaca sayısını döner."""
        added = 0
        while len(self.files()) < self.size:
            seen = set(self.history()) | {
                fingerprint_key(p) for p in map(load_puzzle, self.files()) if p is not None}
            tier = self._rng.choice(PLAY_TIERS)
            p = random_puzzle(tier)
            if fingerprint_key(p) in seen:
                continue
            save_puzzle(self.dir / f"{fingerprint_key(p)}.json", p)
            added += 1
        return added

    def next_puzzle(self) -> Puzzle:
        """Oyuna verilecek bulmaca: havuzdan, yoksa hızlı yoldan. Geçmişe yazılır."""
        p = self.take()
        if p is None:
            seen = set(self.history())
            while True:
                p = random_puzzle()
                if fingerprint_key(p) not in seen:
                    break
        self.mark_seen(p)
        return p
