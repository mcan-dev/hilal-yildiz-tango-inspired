import sqlite3
from datetime import date
from pathlib import Path

import pytest

from game.daily import get_daily_puzzle
from game.db import connect, decode_grid, encode_grid, fill_solutions, pick_solution
from game.rules import all_solutions, is_valid_solution


def test_grid_encoding_and_validation():
    grid = all_solutions(n=4)[0]
    encoded = encode_grid(grid)
    assert len(encoded) == 16 and decode_grid(encoded, 4) == grid
    with pytest.raises(ValueError):
        decode_grid("010", 4)
    with pytest.raises(ValueError):
        encode_grid([[0, 2], [1, 0]])


def test_database_schema_batch_insert_and_seeded_pick(tmp_path):
    con = connect(tmp_path / "game.sqlite3")
    try:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"solutions", "puzzles"} <= tables
        assert con.execute("PRAGMA index_list(solutions)").fetchall()
        grids = all_solutions(n=4)
        assert fill_solutions(con, 4, grids) == 90
        assert fill_solutions(con, 4, grids) == 0
        first = pick_solution(con, 4, 1234)
        assert first == pick_solution(con, 4, 1234)
        assert is_valid_solution(first, n=4)
    finally:
        con.close()


def test_pick_solution_creates_valid_8x8_once(tmp_path):
    path = tmp_path / "game.sqlite3"
    con = connect(path)
    try:
        first = pick_solution(con, 8, 20500101)
        assert first == pick_solution(con, 8, 20500101)
        assert is_valid_solution(first, n=8)
        assert con.execute("SELECT COUNT(*) FROM solutions WHERE n = 8").fetchone()[0] == 1
    finally:
        con.close()


def test_daily_puzzle_is_cached_per_date_and_size(tmp_path):
    database = Path(tmp_path) / "game.sqlite3"
    day = date(2026, 11, 9)
    first = get_daily_puzzle(day, 4, database)
    second = get_daily_puzzle(day, 4, database)
    assert first.n == 4 and first.fingerprint == second.fingerprint
    con = connect(database)
    try:
        assert con.execute("SELECT COUNT(*) FROM solutions WHERE n = 4").fetchone()[0] == 90
        assert con.execute("SELECT COUNT(*) FROM solutions WHERE n = 6").fetchone()[0] == 11222
        assert con.execute(
            "SELECT COUNT(*) FROM puzzles WHERE n = 4 AND date = ?",
            (day.isoformat(),),
        ).fetchone()[0] == 1
    finally:
        con.close()
