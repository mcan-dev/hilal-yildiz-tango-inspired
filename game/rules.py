"""Oyun kuralları: satır/sütun doğrulama, üçlü kontrolü, işaret (=, ×) kontrolü.

Hücre değerleri: HILAL = 0, YILDIZ = 1, boş = None.
Koordinatlar (satır, sütun) biçimindedir, 0'dan başlar.

Bulmaca modeli (reference/gen.py ile aynı):
    givens: {(r, c): değer}                 # sabit semboller
    links:  {((r, c), (r2, c2)): '=' | 'x'} # komşu iki hücre arasındaki işaret
"""
from __future__ import annotations

import itertools
from functools import lru_cache

N = 6
HALF = N // 2
HILAL = 0
YILDIZ = 1
SYMBOL_NAMES = {HILAL: "hilal", YILDIZ: "yıldız"}
SAME = "="
DIFF = "x"

# Klasik Binairo'daki "iki satır/sütun aynı olamaz" kuralı. Tango'da olup olmadığı
# belirsiz (SPEC §2, §11.1). Mentörle teyit edilene kadar kapalı.
UNIQUE_LINES = False

Cell = tuple[int, int]

CELLS: tuple[Cell, ...] = tuple((r, c) for r in range(N) for c in range(N))
ROW_LINES: tuple[tuple[Cell, ...], ...] = tuple(tuple((r, c) for c in range(N)) for r in range(N))
COL_LINES: tuple[tuple[Cell, ...], ...] = tuple(tuple((r, c) for r in range(N)) for c in range(N))
LINES = ROW_LINES + COL_LINES
# Yatay ve dikey tüm komşu çiftler (6x6 için 60 adet), her zaman (küçük, büyük) sırada.
EDGES: tuple[tuple[Cell, Cell], ...] = tuple(
    ((r, c), (r + dr, c + dc))
    for r in range(N)
    for c in range(N)
    for dr, dc in ((0, 1), (1, 0))
    if r + dr < N and c + dc < N
)


# Boyutun pozitif ve çift olmasını doğrular; kurallar her sembolden eşit sayıda ister.
def _validate_n(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0 or n % 2:
        raise ValueError("tahta boyutu pozitif ve çift bir tam sayı olmalı")
    return n


# Boyuta ait hücre, satır, sütun ve kenar koordinatlarını üretir.
def _geometry(n: int):
    cells = tuple((r, c) for r in range(n) for c in range(n))
    rows = tuple(tuple((r, c) for c in range(n)) for r in range(n))
    cols = tuple(tuple((r, c) for r in range(n)) for c in range(n))
    edges = tuple(
        ((r, c), (r + dr, c + dc))
        for r in range(n)
        for c in range(n)
        for dr, dc in ((0, 1), (1, 0))
        if r + dr < n and c + dc < n
    )
    return cells, rows + cols, edges


# İstenen boyuta ait koordinat kümelerini ve varsayılan 6x6 sabitlerini döndürür.
def geometry(n: int = N):
    _validate_n(n)
    if n == N:
        return CELLS, LINES, EDGES
    return _geometry(n)


# Çizgi indeksini, belirtilen tahtanın okunur satır/sütun adına çevirir.
def line_name(index: int, n: int = N) -> str:
    """LINES içindeki indeks için okunur ad: '3. satır', '2. sütun'."""
    _validate_n(n)
    return f"{index + 1}. satır" if index < n else f"{index - n + 1}. sütun"


# İşaret kenarını hücre koordinatlarına göre tek bir sıraya normalleştirir.
def norm_edge(a: Cell, b: Cell) -> tuple[Cell, Cell]:
    return (a, b) if a <= b else (b, a)


# Kısmi çizgilerde sembol sayısı sınırını ve ardışık üçlüleri denetler.
def line_ok(values, n: int | None = None) -> bool:
    """Kısmen dolu bir satırın/sütunun kurallara aykırı olmadığını kontrol eder.

    None değerler boş kabul edilir. Her sembol n/2'yi aşamaz ve yan yana üç
    aynı sembol olamaz.
    """
    values = list(values)
    if n is None:
        n = len(values)
    _validate_n(n)
    if len(values) != n:
        raise ValueError(f"satır uzunluğu {n} olmalı")
    half = n // 2
    if values.count(HILAL) > half or values.count(YILDIZ) > half:
        return False
    for i in range(n - 2):
        a, b, c = values[i : i + 3]
        if a is not None and a == b == c:
            return False
    return True


@lru_cache(maxsize=None)
# Aynı boyut için satır desenlerini tekrar üretmemek üzere önbelleğe alır.
def valid_rows(n: int = N) -> tuple[tuple[int, ...], ...]:
    """Tek satır için tüm geçerli dizilimleri (6 hücrede 14 adet) döndürür."""
    _validate_n(n)
    half = n // 2
    return tuple(
        row
        for row in itertools.product((HILAL, YILDIZ), repeat=n)
        if sum(row) == half and line_ok(row, n)
    )


# Tam çözüm ızgarasının boyuta bağlı bütün satır/sütun kurallarını denetler.
def is_valid_solution(
    grid, unique_lines: bool | None = None, *, n: int | None = None
) -> bool:
    """Tamamen dolu ızgara yazılı kuralların hepsini sağlıyor mu?"""
    if n is None:
        n = len(grid)
    _validate_n(n)
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    if len(grid) != n or any(len(row) != n for row in grid):
        return False
    rows = [tuple(grid[r][c] for c in range(n)) for r in range(n)]
    cols = [tuple(grid[r][c] for r in range(n)) for c in range(n)]
    half = n // 2
    for line in rows + cols:
        if any(v not in (HILAL, YILDIZ) for v in line):
            return False
        if line.count(HILAL) != half or not line_ok(line, n):
            return False
    if unique_lines and (len(set(rows)) != n or len(set(cols)) != n):
        return False
    return True


# Geçerli tahtaları satır satır üretir; n=8 için tüm çözümleri belleğe yüklemez.
def iter_solutions(n: int = N, unique_lines: bool = False, limit: int | None = None,
                   rng=None):
    _validate_n(n)
    rows = valid_rows(n)
    half = n // 2
    grid: list[tuple[int, ...]] = []
    emitted = 0

    def rec():
        nonlocal emitted
        if limit is not None and emitted >= limit:
            return
        if len(grid) == n:
            if is_valid_solution(grid, unique_lines, n=n):
                emitted += 1
                yield tuple(grid)
            return
        candidates = list(rows)
        if rng is not None:
            rng.shuffle(candidates)
        for row in candidates:
            if unique_lines and row in grid:
                continue
            grid.append(row)
            k = len(grid)
            valid = True
            for c in range(n):
                column = [grid[r][c] for r in range(k)]
                ones = sum(column)
                if ones > half or k - ones > half:
                    valid = False
                    break
                if k >= 3 and column[-1] == column[-2] == column[-3]:
                    valid = False
                    break
            if valid:
                yield from rec()
            grid.pop()
            if limit is not None and emitted >= limit:
                return

    yield from rec()


@lru_cache(maxsize=None)
# Satır desenlerinden geçerli tam tahtaları üretir ve sonuçları önbelleğe alır.
def all_solutions(
    unique_lines: bool | None = None, *, n: int = N
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Belirtilen boyuttaki tüm geçerli çözüm ızgaralarını döndürür."""
    _validate_n(n)
    if unique_lines is None:
        unique_lines = UNIQUE_LINES
    return tuple(iter_solutions(n, unique_lines))


# Çözüm ızgarasının sabit sembol ve komşuluk işaretleriyle uyuştuğunu denetler.
def respects_clues(
    grid, givens: dict, links: dict, *, n: int | None = None
) -> bool:
    """Izgara verilen sabit sembollere ve işaretlere uyuyor mu?"""
    if n is None:
        n = len(grid)
    _validate_n(n)
    for (r, c), v in givens.items():
        if grid[r][c] != v:
            return False
    for (a, b), t in links.items():
        same = grid[a[0]][a[1]] == grid[b[0]][b[1]]
        if same != (t == SAME):
            return False
    return True


# Kısmi tahtadaki adet, üçlü ve işaret ihlallerini hücrelerle birlikte bulur.
def violations(
    board, links: dict | None = None, *, n: int | None = None
) -> list[tuple[str, tuple[Cell, ...]]]:
    """Kısmen dolu tahtadaki kural ihlalleri (arayüzde anlık hata gösterimi için).

    Döner: [(tür, hücreler)], tür ∈ {'count', 'triple', 'sign'}.
    """
    if n is None:
        n = len(board)
    _validate_n(n)
    if len(board) != n or any(len(row) != n for row in board):
        raise ValueError(f"tahta {n}x{n} olmalı")
    _, lines, _ = _geometry(n)
    half = n // 2
    out: list[tuple[str, tuple[Cell, ...]]] = []
    for line in lines:
        vals = [board[r][c] for r, c in line]
        for v in (HILAL, YILDIZ):
            if vals.count(v) > half:
                out.append(("count", tuple(cell for cell, x in zip(line, vals) if x == v)))
        for i in range(n - 2):
            a, b, c = vals[i : i + 3]
            if a is not None and a == b == c:
                out.append(("triple", line[i : i + 3]))
    for (a, b), t in (links or {}).items():
        va, vb = board[a[0]][a[1]], board[b[0]][b[1]]
        if va is not None and vb is not None and (va == vb) != (t == SAME):
            out.append(("sign", (a, b)))
    return out
