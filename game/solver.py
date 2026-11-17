"""Çözücüler.

1. Tam çözüm sayacı (kaba kuvvet): tüm geçerli ızgaraları bellekte tutar ve
   ipuçlarına uyanları sayar. Izgaralar bit maskesi olarak saklandığı için hızlıdır.
2. Mantık çözücüsü (tahminsiz): teknikleri en basitten başlayarak uygular. Her
   turda yalnızca o anda uygulanabilen en basit teknik kullanılır. Böylece
   çözüm yolu bir insanın izleyeceği yola benzer ve zorluk puanlamasında kullanılır.

Teknik seviyeleri (SPEC §5):
    1  sign          tek bilinen hücre üzerinden doğrudan = / × aktarımı
    1  pair          ●●_  -> boşluk ters
    2  gap           ●_●  -> orta ters
    3  count         satır/sütunda 3'e ulaşan sembolün kalanı ters
    4  line / chain  satır analizi: satırdaki = / × işaretleriyle birlikte geçerli
                     tüm dizilimlerde aynı kalan hücreler ("chain": sonuç işaretler
                     sayesinde çıkıyorsa, "line": işaretsiz de çıkıyorsa)
    5  contradiction varsayım ve çelişki: hücreye bir değer verilir, 1-4. seviye
                     tekniklerle ilerlenir, çelişki çıkarsa diğer değer doğrudur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .rules import (
    DIFF,
    HILAL,
    N,
    SAME,
    SYMBOL_NAMES,
    YILDIZ,
    Cell,
    UNIQUE_LINES,
    geometry,
    iter_solutions,
    line_name,
    norm_edge,
    valid_rows,
)

TECHNIQUE_LEVELS = {
    "sign": 1,
    "pair": 1,
    "gap": 2,
    "count": 3,
    "line": 4,
    "chain": 4,
    "contradiction": 5,
}
MAX_LEVEL = 5

# ---------------------------------------------------------------------------
# 1) Tam çözüm sayacı
# ---------------------------------------------------------------------------

# İpucu koordinatlarından boyutu çıkarır; boş ve eski çağrılarda 6x6'yı korur.
def _infer_n(givens: dict, links: dict, board=None, n: int | None = None) -> int:
    if n is not None:
        geometry(n)
        return n
    if board is not None:
        size = len(board)
        geometry(size)
        return size
    cells = list(givens)
    cells.extend(cell for edge in links for cell in edge)
    if not cells:
        return N
    size = max(N, max(max(cell) for cell in cells) + 1)
    geometry(size)
    return size


# Verilen satır adaylarının şimdiye kadarki sütun kurallarını koruduğunu denetler.
def _columns_ok(grid, n: int) -> bool:
    half = n // 2
    k = len(grid)
    for c in range(n):
        column = [grid[r][c] for r in range(k)]
        ones = sum(column)
        if ones > half or k - ones > half:
            return False
        if k >= 3 and column[-1] == column[-2] == column[-3]:
            return False
    return True


# Verilen ipuçlarına uyan tahtaları satır satır geri izleyerek sayar.
def _search_solutions(givens: dict, links: dict, n: int, cap: int,
                      unique_lines: bool, collect: bool = False):
    cells, _, _ = geometry(n)
    rows = valid_rows(n)
    by_row = [dict() for _ in range(n)]
    for (r, c), value in givens.items():
        if not (0 <= r < n and 0 <= c < n) or value not in (HILAL, YILDIZ):
            return [] if collect else 0
        by_row[r][c] = value
    normalized_links = [(norm_edge(a, b), kind) for (a, b), kind in links.items()]
    if any(a not in cells or b not in cells or kind not in (SAME, DIFF)
           for (a, b), kind in normalized_links):
        return [] if collect else 0

    grid: list[tuple[int, ...]] = []
    out = []
    count = 0

    def rec(r: int):
        nonlocal count
        if count >= cap:
            return
        if r == n:
            if unique_lines:
                cols = [tuple(grid[i][c] for i in range(n)) for c in range(n)]
                if len(set(cols)) != n:
                    return
            count += 1
            if collect:
                out.append(tuple(grid))
            return
        for row in rows:
            if any(row[c] != value for c, value in by_row[r].items()):
                continue
            if unique_lines and row in grid:
                continue
            valid = True
            for (a, b), kind in normalized_links:
                (r1, c1), (r2, c2) = a, b
                if r1 > r or r2 > r:
                    continue
                va = row[c1] if r1 == r else grid[r1][c1]
                vb = row[c2] if r2 == r else grid[r2][c2]
                if (va == vb) != (kind == SAME):
                    valid = False
                    break
            if not valid:
                continue
            grid.append(row)
            if _columns_ok(grid, n):
                rec(r + 1)
            grid.pop()
            if count >= cap:
                return

    rec(0)
    return out if collect else count


# Eski sözlüksel çağrıları ve count_solutions(n, givens, links) biçimini destekler.
def _parse_solver_args(givens_or_n, links_or_givens, links, cap, unique_lines):
    if isinstance(givens_or_n, int):
        n = givens_or_n
        givens = links_or_givens
        actual_links = links or {}
    else:
        n = None
        givens = givens_or_n
        actual_links = links_or_givens or {}
        if links is not None:
            cap = links
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("cap pozitif bir tam sayı olmalı")
    return _infer_n(givens, actual_links, n=n), givens, actual_links, cap, unique_lines


def find_solutions(givens: dict, links: dict, cap: int | None = None,
                   unique_lines: bool | None = None, *, n: int | None = None) -> list:
    """İpuçlarına uyan çözümleri geri izlemeyle bulur (isteğe bağlı adet sınırı)."""
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    size = _infer_n(givens, links, n=n)
    return _search_solutions(givens, links, size, cap or 2**31, unique_lines, collect=True)


def count_solutions(givens_or_n, links_or_givens, links=None, cap: int = 2,
                    unique_lines: bool | None = None, *, n: int | None = None) -> int:
    """Satır bazlı geri izlemeyle çözüm sayar; sayım `cap` sınırında kesilir."""
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("cap pozitif bir tam sayı olmalı")
    if isinstance(givens_or_n, int):
        size, givens, actual_links = givens_or_n, links_or_givens, links or {}
    else:
        size = n
        givens, actual_links = givens_or_n, links_or_givens or {}
        if links is not None:
            cap = links
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("cap pozitif bir tam sayı olmalı")
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    size = _infer_n(givens, actual_links, n=size)
    return _search_solutions(givens, actual_links, size, cap, unique_lines)


# ---------------------------------------------------------------------------
# 2) Mantık çözücüsü
# ---------------------------------------------------------------------------


class Contradiction(Exception):
    """Tahta kurallarla çelişiyor (hiçbir çözüm kalmadı)."""


@dataclass(frozen=True)
class Move:
    cell: Cell
    value: int
    technique: str
    level: int
    reason: str
    # Çıkarımın dayandığı hücreler (ipucunda vurgulanır; ör. çiftin iki hücresi).
    because: tuple = ()


@dataclass
class SolveResult:
    board: list
    solved: bool
    steps: list = field(default_factory=list)
    contradiction: bool = False

    @property
    def max_level(self) -> int:
        return max((m.level for m in self.steps), default=0)

    def technique_counts(self) -> dict:
        out: dict[str, int] = {}
        for m in self.steps:
            out[m.technique] = out.get(m.technique, 0) + 1
        return out


def _cell_name(cell: Cell) -> str:
    return f"({cell[0] + 1}. satır, {cell[1] + 1}. sütun)"


# Çizgi indeksinden satır/sütun ekindeki doğru sözcüğü seçer.
def _line_word(index: int, n: int = N) -> str:
    return "satırda" if index < n else "sütunda"


class _Ctx:
    """Bir bulmacanın işaretlerinden türetilen, çözüm boyunca sabit bilgiler."""

    def __init__(self, links: dict, n: int = N):
        self.n = n
        self.half = n // 2
        self.cells, self.lines, _ = geometry(n)
        self.rows = valid_rows(n)
        self.links = {norm_edge(a, b): t for (a, b), t in links.items()}
        self.line_links = []
        for line in self.lines:
            pos = {cell: i for i, cell in enumerate(line)}
            self.line_links.append(
                [(pos[a], pos[b], t) for (a, b), t in self.links.items() if a in pos and b in pos]
            )


def _broken(board, ctx: _Ctx) -> bool:
    for line in ctx.lines:
        vals = [board[r][c] for r, c in line]
        if vals.count(HILAL) > ctx.half or vals.count(YILDIZ) > ctx.half:
            return True
        for i in range(ctx.n - 2):
            if vals[i] is not None and vals[i] == vals[i + 1] == vals[i + 2]:
                return True
    for (a, b), t in ctx.links.items():
        va, vb = board[a[0]][a[1]], board[b[0]][b[1]]
        if va is not None and vb is not None and (va == vb) != (t == SAME):
            return True
    return False


def _level1(board, ctx: _Ctx) -> list[Move]:
    moves = []
    for (a, b), t in ctx.links.items():
        for x, y in ((a, b), (b, a)):
            vx, vy = board[x[0]][x[1]], board[y[0]][y[1]]
            if vx is not None and vy is None:
                v = vx if t == SAME else 1 - vx
                if t == SAME:
                    why = f"= işareti: {_cell_name(x)} {SYMBOL_NAMES[vx]}, bu hücre de aynı olmalı."
                else:
                    why = (f"× işareti: {_cell_name(x)} {SYMBOL_NAMES[vx]}, bu hücre farklı "
                           f"olmalı → {SYMBOL_NAMES[v]}.")
                moves.append(Move(y, v, "sign", 1, why, (x,)))
    for li, line in enumerate(ctx.lines):
        vals = [board[r][c] for r, c in line]
        for i in range(ctx.n - 1):
            a, b = vals[i], vals[i + 1]
            if a is None or a != b:
                continue
            for j in (i - 1, i + 2):
                if 0 <= j < ctx.n and vals[j] is None:
                    moves.append(Move(line[j], 1 - a, "pair", 1,
                                      f"Çift kuralı ({line_name(li, ctx.n)}): yan yana iki "
                                      f"{SYMBOL_NAMES[a]} var, üçüncüsü gelemez → "
                                      f"{SYMBOL_NAMES[1 - a]}.",
                                      (line[i], line[i + 1])))
    return moves


def _level2(board, ctx: _Ctx) -> list[Move]:
    moves = []
    for li, line in enumerate(ctx.lines):
        vals = [board[r][c] for r, c in line]
        for i in range(ctx.n - 2):
            a, m, b = vals[i : i + 3]
            if a is not None and a == b and m is None:
                moves.append(Move(line[i + 1], 1 - a, "gap", 2,
                                  f"Boşluk kuralı ({line_name(li, ctx.n)}): iki {SYMBOL_NAMES[a]} "
                                  f"arasındaki hücre {SYMBOL_NAMES[1 - a]} olmalı.",
                                  (line[i], line[i + 2])))
    return moves


def _level3(board, ctx: _Ctx) -> list[Move]:
    moves = []
    for li, line in enumerate(ctx.lines):
        vals = [board[r][c] for r, c in line]
        for v in (HILAL, YILDIZ):
            if vals.count(v) == ctx.half:
                trio = tuple(cell for cell, x in zip(line, vals) if x == v)
                for cell, x in zip(line, vals):
                    if x is None:
                        moves.append(Move(cell, 1 - v, "count", 3,
                                          f"Sayma kuralı ({line_name(li, ctx.n)}): bu "
                                          f"{_line_word(li, ctx.n)} zaten {ctx.half} "
                                          f"{SYMBOL_NAMES[v]} var → "
                                          f"{SYMBOL_NAMES[1 - v]}.", trio))
    return moves


@lru_cache(maxsize=32768)
def _candidate_rows(vals: tuple, line_links: tuple, n: int) -> tuple:
    """Tekrarlanan ipucu denetimleri için uyumlu satır desenlerini önbelleğe alır."""
    out = []
    for row in valid_rows(n):
        if any(v is not None and v != x for v, x in zip(vals, row)):
            continue
        if any((row[i] == row[j]) != (t == SAME) for i, j, t in line_links):
            continue
        out.append(row)
    return tuple(out)


# Bir çizgi için sabit ve işaretlerle uyumlu satır desenlerini döndürür.
def _candidates(vals, line_links, ctx: _Ctx) -> tuple:
    return _candidate_rows(tuple(vals), tuple(line_links), ctx.n)


def _forced(cands, vals) -> dict[int, int]:
    out = {}
    for i, v in enumerate(vals):
        if v is None:
            seen = {row[i] for row in cands}
            if len(seen) == 1:
                out[i] = seen.pop()
    return out


def _level4(board, ctx: _Ctx) -> list[Move]:
    moves = []
    for li, line in enumerate(ctx.lines):
        vals = [board[r][c] for r, c in line]
        cands = _candidates(vals, ctx.line_links[li], ctx)
        if not cands:
            raise Contradiction(f"{line_name(li, ctx.n)} için geçerli dizilim kalmadı")
        forced = _forced(cands, vals)
        if not forced:
            continue
        plain = _forced(_candidates(vals, (), ctx), vals) if ctx.line_links[li] else forced
        known = tuple(cell for cell, x in zip(line, vals) if x is not None)
        for i, v in forced.items():
            if plain.get(i) == v:
                moves.append(Move(line[i], v, "line", 4,
                                  f"Satır analizi ({line_name(li, ctx.n)}): bu "
                                  f"{_line_word(li, ctx.n)} "
                                  f"{ctx.half} hilal / {ctx.half} yıldız ve üçlü yasağına uyan tüm "
                                  f"dizilimlerde bu hücre {SYMBOL_NAMES[v]}.", known))
            else:
                moves.append(Move(line[i], v, "chain", 4,
                                  f"= / × zinciri ({line_name(li, ctx.n)}): işaretlerle birlikte "
                                  f"geçerli tüm dizilimlerde bu hücre {SYMBOL_NAMES[v]}.", known))
    return moves


# Daha kısıtlı hücrelerden başlayıp varsayım-çelişki hamlesini arar.
def _level5(board, ctx: _Ctx) -> list[Move]:
    def constraint_score(cell: Cell) -> int:
        r, c = cell
        score = sum(value is not None for value in board[r])
        score += sum(board[row][c] is not None for row in range(ctx.n))
        for (a, b), _kind in ctx.links.items():
            if a == cell and board[b[0]][b[1]] is not None:
                score += 2
            elif b == cell and board[a[0]][a[1]] is not None:
                score += 2
        return score

    candidates = sorted(
        (cell for cell in ctx.cells if board[cell[0]][cell[1]] is None),
        key=constraint_score,
        reverse=True,
    )
    for cell in candidates:
        r, c = cell
        bad = []
        for v in (HILAL, YILDIZ):
            trial = [row[:] for row in board]
            trial[r][c] = v
            try:
                _fixpoint(trial, ctx, 4)
            except Contradiction:
                bad.append(v)
        if len(bad) == 2:
            raise Contradiction(f"{_cell_name(cell)} iki değerle de çelişiyor")
        if bad:
            v = bad[0]
            return [Move(cell, 1 - v, "contradiction", 5,
                         f"Varsayım ve çelişki: bu hücre {SYMBOL_NAMES[v]} olsaydı ilerleyen "
                         f"adımlarda çelişki çıkardı → {SYMBOL_NAMES[1 - v]}.")]
    return []


_FINDERS = {1: _level1, 2: _level2, 3: _level3, 4: _level4, 5: _level5}


def _apply(board, moves: list[Move]) -> list[Move]:
    """Hamleleri uygular (aynı hücreye gelen tekrarları atar). Çelişkide hata verir."""
    applied = []
    for m in moves:
        r, c = m.cell
        cur = board[r][c]
        if cur is None:
            board[r][c] = m.value
            applied.append(m)
        elif cur != m.value:
            raise Contradiction(f"{_cell_name(m.cell)} için çelişen sonuçlar")
    return applied


def _round(board, ctx: _Ctx, max_level: int) -> list[Move]:
    """En basit uygulanabilir seviyedeki tüm hamleleri bulur ve uygular."""
    for level in range(1, max_level + 1):
        moves = _FINDERS[level](board, ctx)
        if moves:
            applied = _apply(board, moves)
            if _broken(board, ctx):
                raise Contradiction("kural ihlali")
            return applied
    return []


def _fixpoint(board, ctx: _Ctx, max_level: int) -> None:
    if _broken(board, ctx):
        raise Contradiction("kural ihlali")
    while _round(board, ctx, max_level):
        pass


# Sabit hücrelerden belirtilen boyutta boş tahta üretir.
def board_from_givens(givens: dict, n: int | None = None) -> list:
    n = _infer_n(givens, {}, n=n)
    board = [[None] * n for _ in range(n)]
    for (r, c), v in givens.items():
        board[r][c] = v
    return board


# Tahtanın tüm hücreleri doldurulmuş olup olmadığını bildirir.
def is_solved(board) -> bool:
    return all(x is not None for row in board for x in row)


def solve(givens: dict, links: dict, max_level: int = MAX_LEVEL, board=None,
          *, n: int | None = None) -> SolveResult:
    """Tahminsiz mantık çözücüsü.

    Her turda en basit uygulanabilir tekniği kullanır. `board` verilirse oradan
    devam eder (oyuncunun mevcut tahtası). Dönen `steps` uygulanan tüm hamlelerdir.
    """
    size = _infer_n(givens, links, board=board, n=n)
    ctx = _Ctx(links, size)
    b = [row[:] for row in board] if board is not None else board_from_givens(givens, size)
    steps: list[Move] = []
    try:
        if _broken(b, ctx):
            raise Contradiction("kural ihlali")
        while True:
            applied = _round(b, ctx, max_level)
            if not applied:
                break
            steps.extend(applied)
    except Contradiction:
        return SolveResult(b, False, steps, contradiction=True)
    return SolveResult(b, is_solved(b), steps)


# Mevcut tahtada kullanılabilecek en basit zorunlu hamleyi döndürür.
def next_move(board, links: dict, max_level: int = MAX_LEVEL) -> Move | None:
    """İpucu butonu için: mevcut tahtadan bir sonraki zorunlu hamle (en basit teknikle).

    Tahta çelişkiliyse Contradiction, hamle bulunamazsa None döner.
    """
    ctx = _Ctx(links, len(board))
    if _broken(board, ctx):
        raise Contradiction("kural ihlali")
    for level in range(1, max_level + 1):
        moves = _FINDERS[level](board, ctx)
        if moves:
            return moves[0]
    return None


# Bulmacanın tahmin kullanmadan çözülebilir olup olmadığını bildirir.
def logic_solvable(givens: dict, links: dict, max_level: int = MAX_LEVEL,
                   *, n: int | None = None) -> bool:
    return solve(givens, links, max_level, n=n).solved


# Eski arayüzle uyumluluk için 1–3. seviye çıkarımlarını uygular.
def propagate(givens: dict, links: dict, *, n: int | None = None):
    """reference/gen.py ile uyumluluk: 1-3. seviye kurallarla sabit noktaya kadar ilerler.

    Döner: (tahta, kullanılan teknik adları kümesi).
    """
    res = solve(givens, links, max_level=3, n=n)
    return res.board, {m.technique for m in res.steps}
