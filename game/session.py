"""Bir oyun oturumunun durumu (arayüzden bağımsız): tahta, geri al/yinele, ipucu."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .generator import Puzzle
from .rules import HILAL, N, YILDIZ, Cell, geometry, violations
from .solver import Move, board_from_givens, next_move

CYCLE = (None, HILAL, YILDIZ)  # boş -> hilal -> yıldız -> boş


@dataclass(frozen=True)
class Hint:
    cell: Cell
    value: int | None   # None: hücre hatalı, temizlenmeli
    reason: str
    move: Move | None = None


class GameSession:
    def __init__(self, puzzle: Puzzle, clock=time.monotonic):
        self.puzzle = puzzle
        self.n = puzzle.n
        self.cells, _, _ = geometry(self.n)
        self.board = board_from_givens(puzzle.givens, self.n)
        self._undo: list[list[tuple[Cell, int | None, int | None]]] = []
        self._redo: list[list[tuple[Cell, int | None, int | None]]] = []
        self.moves = 0
        self.undos = 0
        self.hints = 0
        self._clock = clock
        self._start = clock()
        self._finished_at: float | None = None

    # --- durum -----------------------------------------------------------
    def is_fixed(self, cell: Cell) -> bool:
        return cell in self.puzzle.givens

    def value(self, cell: Cell) -> int | None:
        return self.board[cell[0]][cell[1]]

    def is_complete(self) -> bool:
        """Tahta dolu ve hiçbir kural bozulmuyor mu? (Tango gibi kurala göre kontrol.)

        Bulmacanın tek çözümü olduğu için bu, saklanan çözümle aynı olmak demektir;
        yine de çözümle karşılaştırmak yerine kurallar denetlenir ki oyuncunun
        kurallara uyan her doğru tahtası kesinlikle kabul edilsin.
        """
        if any(self.board[r][c] is None for r, c in self.cells):
            return False
        return not violations(self.board, self.puzzle.links, n=self.n)

    @property
    def finished(self) -> bool:
        return self._finished_at is not None

    def elapsed(self) -> int:
        end = self._finished_at if self._finished_at is not None else self._clock()
        return int(end - self._start)

    def error_cells(self) -> set[Cell]:
        """Kural ihlaline karışan hücreler (çözümü açık etmez)."""
        out: set[Cell] = set()
        for kind, cells in violations(self.board, self.puzzle.links, n=self.n):
            out.update(cells)
        return out

    def broken_links(self) -> set:
        return {tuple(cells) for kind, cells in violations(self.board, self.puzzle.links, n=self.n)
                if kind == "sign"}

    # --- hamleler --------------------------------------------------------
    def _apply(self, changes) -> None:
        for (r, c), _old, new in changes:
            self.board[r][c] = new
        if self.is_complete() and self._finished_at is None:
            self._finished_at = self._clock()

    def set(self, cell: Cell, value: int | None) -> bool:
        if self.finished or self.is_fixed(cell) or self.value(cell) == value:
            return False
        change = [(cell, self.value(cell), value)]
        self._apply(change)
        self._undo.append(change)
        self._redo.clear()
        self.moves += 1
        return True

    def cycle(self, cell: Cell, step: int = 1) -> bool:
        i = CYCLE.index(self.value(cell))
        return self.set(cell, CYCLE[(i + step) % len(CYCLE)])

    def clear(self) -> bool:
        if self.finished:
            return False
        change = [((r, c), self.board[r][c], None) for r, c in self.cells
                  if not self.is_fixed((r, c)) and self.board[r][c] is not None]
        if not change:
            return False
        self._apply(change)
        self._undo.append(change)
        self._redo.clear()
        return True

    def can_undo(self) -> bool:
        return bool(self._undo) and not self.finished

    def can_redo(self) -> bool:
        return bool(self._redo) and not self.finished

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        change = self._undo.pop()
        self._apply([(cell, new, old) for cell, old, new in reversed(change)])
        self._redo.append(change)
        self.undos += 1
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        change = self._redo.pop()
        self._apply(change)
        self._undo.append(change)
        return True

    # --- ipucu -----------------------------------------------------------
    def hint(self) -> Hint | None:
        """Önce çözümle uyuşmayan bir hücreyi, yoksa bir sonraki zorunlu hamleyi gösterir."""
        if self.finished:
            return None
        sol = self.puzzle.solution
        for r, c in self.cells:
            v = self.board[r][c]
            if v is not None and v != sol[r][c]:
                self.hints += 1
                return Hint((r, c), None, "Bu hücre çözümle uyuşmuyor. Temizleyip yeniden düşünün.")
        move = next_move(self.board, self.puzzle.links)
        if move is None:
            return None
        self.hints += 1
        return Hint(move.cell, move.value, move.reason, move)
