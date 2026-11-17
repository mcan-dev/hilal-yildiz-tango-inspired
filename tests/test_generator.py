import pytest

from game.difficulty import TIER_MAX_LEVEL, TIERS
from game.generator import generate, is_minimal, quality_issues
from game.rules import is_valid_solution, respects_clues
from game.solver import count_solutions, solve

SEEDS = range(6)


@pytest.fixture(scope="module")
def puzzles():
    return {(tier, s): generate(s, tier) for tier in TIERS for s in SEEDS}


def test_unique_solution(puzzles):
    for p in puzzles.values():
        assert count_solutions(p.givens, p.links, cap=10**6) == 1
        assert is_valid_solution(p.solution)
        assert respects_clues(p.solution, p.givens, p.links)


def test_logic_solver_solves_without_guessing(puzzles):
    for p in puzzles.values():
        res = solve(p.givens, p.links, max_level=p.level)
        assert res.solved
        assert [list(r) for r in p.solution] == res.board


def test_minimal(puzzles):
    """Herhangi bir ipucu çıkarılınca bulmaca bozulmalı."""
    for p in puzzles.values():
        assert is_minimal(p), p.seed


def test_target_tier_and_quality(puzzles):
    for (tier, _), p in puzzles.items():
        assert p.tier == tier and not p.notes
        assert p.level == TIER_MAX_LEVEL[tier]
        assert quality_issues(p.givens, p.links) == []


def test_seed_determinism():
    for tier in TIERS:
        a, b = generate(99, tier), generate(99, tier)
        assert a.fingerprint == b.fingerprint and a.solution == b.solution


def test_exclude_prevents_repeat():
    a = generate(5, "orta")
    b = generate(5, "orta", exclude={a.fingerprint})
    assert b.fingerprint != a.fingerprint


def test_quality_filter_catches_bad_puzzles():
    # Hiç işaret yok, tek köşeye yığılmış ipuçları
    givens = {(0, 0): 0, (0, 1): 0, (1, 0): 1}
    issues = quality_issues(givens, {})
    assert any("işaret" in i for i in issues)
    assert any("dağılım" in i for i in issues)
