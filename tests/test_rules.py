import pytest

from game.rules import (
    EDGES, HILAL, LINES, YILDIZ, all_solutions, is_valid_solution, line_ok,
    respects_clues, valid_rows, violations,
)


def test_row_patterns():
    rows = valid_rows()
    assert len(rows) == 14
    assert len(set(rows)) == 14
    assert len(valid_rows(6)) == 14


def test_rules_support_even_board_sizes():
    rows = valid_rows(4)
    assert len(rows) == 6
    assert all(len(row) == 4 and row.count(0) == row.count(1) == 2 for row in rows)
    assert len(all_solutions(n=4)) == 90
    assert all(is_valid_solution(grid, n=4) for grid in all_solutions(n=4))
    assert line_ok([0, 0, 1, None], n=4)
    assert not line_ok([0, 0, 0, None], n=4)


@pytest.mark.parametrize("n", [0, 3, 5, -4])
def test_rules_reject_non_positive_or_odd_board_sizes(n):
    with pytest.raises(ValueError):
        valid_rows(n)
    with pytest.raises(ValueError):
        all_solutions(n=n)


def test_solution_count_is_11222():
    assert len(all_solutions(False)) == 11222


def test_unique_lines_count_is_4140():
    assert len(all_solutions(True)) == 4140


def test_every_grid_satisfies_rules():
    sols = all_solutions(False)
    assert len(set(sols)) == len(sols)
    for g in sols:
        assert is_valid_solution(g, unique_lines=False)
        for line in LINES:
            vals = [g[r][c] for r, c in line]
            assert vals.count(HILAL) == vals.count(YILDIZ) == 3
            assert all(not (vals[i] == vals[i + 1] == vals[i + 2]) for i in range(4))


def test_unique_lines_subset():
    assert set(all_solutions(True)) <= set(all_solutions(False))
    for g in all_solutions(True):
        assert len(set(g)) == 6 and len(set(zip(*g))) == 6


def test_invalid_grids_rejected():
    g = [list(r) for r in all_solutions(False)[0]]
    g[0][0] = 1 - g[0][0]  # sayıları bozar
    assert not is_valid_solution(g)
    assert not line_ok([0, 0, 0, None, None, None])
    assert not line_ok([0, 1, 0, 0, 0, None])  # 4 hilal
    assert line_ok([0, 0, None, 1, None, None])


def test_edges_and_clue_check():
    assert len(EDGES) == 60
    g = all_solutions(False)[123]
    links = {(a, b): "=" if g[a[0]][a[1]] == g[b[0]][b[1]] else "x" for a, b in EDGES}
    assert respects_clues(g, {(0, 0): g[0][0]}, links)
    assert not respects_clues(g, {(0, 0): 1 - g[0][0]}, {})


def test_violations_reports_triples_counts_and_signs():
    b = [[None] * 6 for _ in range(6)]
    b[0][0] = b[0][1] = b[0][2] = HILAL
    b[1][0], b[1][1] = HILAL, YILDIZ
    kinds = {k for k, _ in violations(b, {((1, 0), (1, 1)): "="})}
    assert kinds == {"triple", "sign"}
