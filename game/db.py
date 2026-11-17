"""SQLite persistence for solution grids and daily puzzles."""
from __future__ import annotations

import json
import os
import random
import sqlite3
from pathlib import Path

from .rules import all_solutions, iter_solutions


def default_db_path() -> Path:
    """Return the shared application data path for the SQLite game database."""
    root = os.environ.get("HILAL_YILDIZ_HOME")
    return (Path(root) if root else Path.home() / ".hilal_yildiz") / "game.sqlite3"


def encode_grid(grid) -> str:
    """Encode a square binary grid as row-major zero/one text."""
    n = len(grid)
    if n not in (4, 6, 8) or any(len(row) != n for row in grid):
        raise ValueError("grid must be square with size 4, 6, or 8")
    if any(value not in (0, 1) for row in grid for value in row):
        raise ValueError("grid cells must be zero or one")
    return "".join(str(value) for row in grid for value in row)


def decode_grid(data: str, n: int | None = None) -> tuple[tuple[int, ...], ...]:
    """Decode row-major binary text into an immutable square grid."""
    if n is None:
        n = int(len(data) ** 0.5)
    if n not in (4, 6, 8) or len(data) != n * n or set(data) - {"0", "1"}:
        raise ValueError("encoded grid has invalid size or characters")
    return tuple(tuple(map(int, data[r * n:(r + 1) * n])) for r in range(n))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database and create its schema and size index if needed."""
    db_path = Path(path) if path is not None else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("""
        CREATE TABLE IF NOT EXISTS solutions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            n INTEGER NOT NULL,
            grid TEXT NOT NULL,
            UNIQUE(n, grid)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_solutions_n ON solutions(n)")
    con.execute("""
        CREATE TABLE IF NOT EXISTS puzzles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            n INTEGER NOT NULL,
            date TEXT NOT NULL,
            givens TEXT NOT NULL,
            links TEXT NOT NULL,
            solution TEXT NOT NULL,
            difficulty INTEGER NOT NULL,
            UNIQUE(n, date)
        )
    """)
    con.commit()
    return con


def fill_solutions(con: sqlite3.Connection, n: int, grids) -> int:
    """Insert grids in a batch, ignoring rows already stored."""
    if n not in (4, 6, 8):
        raise ValueError("board size must be 4, 6, or 8")
    rows = []
    for grid in grids:
        if len(grid) != n:
            raise ValueError(f"solution grid must be {n}x{n}")
        rows.append((n, encode_grid(grid)))
    before = con.total_changes
    con.executemany("INSERT OR IGNORE INTO solutions(n, grid) VALUES (?, ?)", rows)
    con.commit()
    return con.total_changes - before


def _ensure_complete_small_solutions(con: sqlite3.Connection, n: int) -> None:
    count = con.execute("SELECT COUNT(*) FROM solutions WHERE n = ?", (n,)).fetchone()[0]
    if count == 0 and n in (4, 6):
        fill_solutions(con, n, all_solutions(n=n))


def pick_solution(con: sqlite3.Connection, n: int, seed) -> tuple[tuple[int, ...], ...]:
    """Pick reproducibly from persisted grids; lazily create a valid 8x8 grid."""
    if n not in (4, 6, 8):
        raise ValueError("board size must be 4, 6, or 8")
    _ensure_complete_small_solutions(con, n)
    if n == 8:
        grid = next(iter_solutions(n=n, rng=random.Random(seed), limit=1), None)
        if grid is None:
            raise RuntimeError("no valid 8x8 solution grid")
        fill_solutions(con, n, (grid,))
        return grid
    rows = con.execute("SELECT grid FROM solutions WHERE n = ? ORDER BY id", (n,)).fetchall()
    encoded = random.Random(seed).choice(rows)[0]
    return decode_grid(encoded, n)


def ensure_database(path: str | Path | None = None) -> None:
    """Create schema and populate the complete 4x4/6x6 solution sets."""
    con = connect(path)
    try:
        _ensure_complete_small_solutions(con, 4)
        _ensure_complete_small_solutions(con, 6)
    finally:
        con.close()


def save_puzzle(con: sqlite3.Connection, n: int, day: str, givens: dict,
                links: dict, solution, difficulty: int) -> None:
    """Store a daily puzzle using JSON clue maps and encoded solution grid."""
    givens_json = json.dumps([[r, c, value] for (r, c), value in sorted(givens.items())])
    links_json = json.dumps([
        [a[0], a[1], b[0], b[1], kind]
        for (a, b), kind in sorted(links.items())
    ])
    con.execute(
        """INSERT OR REPLACE INTO puzzles(n, date, givens, links, solution, difficulty)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (n, day, givens_json, links_json, encode_grid(solution), difficulty),
    )
    con.commit()


def load_puzzle(con: sqlite3.Connection, n: int, day: str):
    """Read a daily puzzle tuple, or return None when it is not cached."""
    row = con.execute(
        "SELECT givens, links, solution, difficulty FROM puzzles WHERE n = ? AND date = ?",
        (n, day),
    ).fetchone()
    if row is None:
        return None
    givens = {(r, c): value for r, c, value in json.loads(row[0])}
    links = {((r1, c1), (r2, c2)): kind
             for r1, c1, r2, c2, kind in json.loads(row[1])}
    return givens, links, decode_grid(row[2], n), row[3]
