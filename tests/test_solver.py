import random

import pytest

from game.generator import _full_clues
from game.rules import CELLS, all_solutions
from game.solver import (
    Contradiction, board_from_givens, count_solutions, find_solutions, next_move, solve,
)


def test_empty_puzzle_counts():
    assert count_solutions({}, {}, cap=10**6) == 11222
    assert count_solutions({}, {}, cap=10**6, unique_lines=True) == 4140
    assert count_solutions({}, {}) == 2  # cap
    with pytest.raises(ValueError):
        count_solutions({}, {}, cap=0)
    with pytest.raises(ValueError):
        count_solutions({}, {}, 0)


def test_4x4_backtracking_count_and_small_puzzles():
    from game.rules import all_solutions
    solution = all_solutions(n=4)[0]
    unique_givens = {(r, c): value for r, row in enumerate(solution)
                     for c, value in enumerate(row)}
    assert count_solutions(4, unique_givens, {}, cap=2) == 1
    assert count_solutions(4, {}, {}, cap=2) == 2
    assert count_solutions({}, {}, cap=1000, n=4) == 90


def test_count_matches_brute_force_filter():
    rng = random.Random(1)
    sols = all_solutions(False)
    for _ in range(20):
        sol = rng.choice(sols)
        givens, links = _full_clues(sol)
        g = dict(rng.sample(sorted(givens.items()), 4))
        l = dict(rng.sample(sorted(links.items()), 4))
        expect = [s for s in sols if all(s[r][c] == v for (r, c), v in g.items())
                  and all((s[a[0]][a[1]] == s[b[0]][b[1]]) == (t == "=") for (a, b), t in l.items())]
        assert count_solutions(g, l, cap=10**6) == len(expect)
        assert sol in find_solutions(g, l)


def test_full_clues_solve_trivially():
    sol = all_solutions(False)[42]
    givens, links = _full_clues(sol)
    res = solve(givens, links)
    assert res.solved and res.steps == []


def test_logic_solver_is_sound():
    """Rastgele kısmi ipuçlarında çözücünün hiçbir hamlesi gerçek çözüme aykırı olmamalı."""
    rng = random.Random(7)
    sols = all_solutions(False)
    for _ in range(40):
        sol = rng.choice(sols)
        givens, links = _full_clues(sol)
        g = dict(rng.sample(sorted(givens.items()), rng.randint(3, 10)))
        l = dict(rng.sample(sorted(links.items()), rng.randint(3, 15)))
        res = solve(g, l)
        assert not res.contradiction
        if count_solutions(g, l) == 1:
            for m in res.steps:
                assert sol[m.cell[0]][m.cell[1]] == m.value, m
        for r, c in CELLS:  # çok çözümlü olsa bile türetilen her değer tüm çözümlerde ortak
            if res.board[r][c] is not None:
                assert all(s[r][c] == res.board[r][c] for s in find_solutions(g, l))


def test_techniques_examples():
    b = [[None] * 6 for _ in range(6)]
    b[0][0] = b[0][1] = 0
    m = next_move(b, {})
    assert (m.technique, m.cell, m.value) == ("pair", (0, 2), 1)

    b = [[None] * 6 for _ in range(6)]
    b[0][0] = b[0][2] = 1
    m = next_move(b, {})
    assert (m.technique, m.cell, m.value) == ("gap", (0, 1), 0)

    b = [[None] * 6 for _ in range(6)]
    b[0][0], b[0][3], b[0][4], b[0][5] = 0, 0, 1, 0  # ☾ _ _ ☾ ★ ☾ : çift/boşluk yok
    m = next_move(b, {})
    assert m.technique == "count" and m.value == 1 and "Sayma" in m.reason

    b = [[None] * 6 for _ in range(6)]
    b[0][0] = 0
    m = next_move(b, {((0, 0), (1, 0)): "x"})
    assert (m.technique, m.cell, m.value) == ("sign", (1, 0), 1)


def test_contradiction_detected():
    b = board_from_givens({(0, 0): 0, (0, 1): 0, (0, 2): 0})
    with pytest.raises(Contradiction):
        next_move(b, {})
    assert solve({(0, 0): 0}, {((0, 0), (0, 1)): "="}, board=b).contradiction


def test_moves_carry_reason_cells():
    b = [[None] * 6 for _ in range(6)]
    b[0][0] = b[0][1] = 0
    m = next_move(b, {})
    assert set(m.because) == {(0, 0), (0, 1)}
    b = [[None] * 6 for _ in range(6)]
    b[0][0] = b[0][2] = 1
    assert set(next_move(b, {}).because) == {(0, 0), (0, 2)}
    b = [[None] * 6 for _ in range(6)]
    b[0][0], b[0][3], b[0][4], b[0][5] = 0, 0, 1, 0
    m = next_move(b, {})
    assert m.technique == "count" and set(m.because) == {(0, 0), (0, 3), (0, 5)}
    b = [[None] * 6 for _ in range(6)]
    b[0][0] = 0
    assert next_move(b, {((0, 0), (1, 0)): "x"}).because == ((0, 0),)
