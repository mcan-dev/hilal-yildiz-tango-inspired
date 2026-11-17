"""Arayüzün arkasındaki mantık: oturum, şekiller, temalar, istatistik, önbellek."""
import json
import math
from datetime import date

import pytest

from game.daily import puzzle_for
from game.generator import Puzzle, generate
from game.rules import CELLS, HILAL, YILDIZ
from game.session import GameSession
from stats.store import StatsStore
from themes.calendar import DEFAULT, TEN_NOVEMBER, theme_for
from ui.shapes import crescent_points, star_points


@pytest.fixture(scope="module")
def puzzle():
    return generate(3, "kolay")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def free_cell(p):
    return next(c for c in CELLS if c not in p.givens)


def test_cycle_and_locked_cells(puzzle):
    s = GameSession(puzzle)
    fixed = next(iter(puzzle.givens))
    assert not s.cycle(fixed)
    cell = free_cell(puzzle)
    seq = []
    for _ in range(3):
        s.cycle(cell)
        seq.append(s.value(cell))
    assert seq == [HILAL, YILDIZ, None]
    s.cycle(cell, -1)
    assert s.value(cell) == YILDIZ


def test_undo_redo(puzzle):
    s = GameSession(puzzle)
    cell = free_cell(puzzle)
    s.set(cell, HILAL)
    s.set(cell, YILDIZ)
    assert s.undo() and s.value(cell) == HILAL
    assert s.undo() and s.value(cell) is None
    assert not s.undo()
    assert s.redo() and s.value(cell) == HILAL
    s.set(cell, None)
    assert not s.redo()  # yeni hamle yineleme yığınını temizler
    assert s.undos == 2


def test_clear_is_one_undo_step(puzzle):
    s = GameSession(puzzle)
    free = [c for c in CELLS if c not in puzzle.givens][:3]
    for c in free:
        s.set(c, HILAL)
    assert s.clear()
    assert all(s.value(c) is None for c in free)
    s.undo()
    assert all(s.value(c) == HILAL for c in free)


def test_hints_solve_the_puzzle(puzzle):
    """Sadece ipuçlarını uygulayarak bulmaca bitmeli (ipucu hep zorunlu hamle verir)."""
    clock = Clock()
    s = GameSession(puzzle, clock=clock)
    while not s.finished:
        h = s.hint()
        assert h is not None and h.value == puzzle.solution[h.cell[0]][h.cell[1]]
        assert h.reason
        s.set(h.cell, h.value)
        clock.t += 1
    assert s.is_complete() and s.hints == s.moves
    assert s.elapsed() == s.hints - 1  # son hamle, saat ilerlemeden bitirdi
    clock.t += 100
    assert s.elapsed() == s.hints - 1  # bitince saat durur
    assert not s.set(free_cell(puzzle), None)  # bitince tahta kilitli


def test_hint_points_out_wrong_cell(puzzle):
    s = GameSession(puzzle)
    cell = free_cell(puzzle)
    s.set(cell, 1 - puzzle.solution[cell[0]][cell[1]])
    h = s.hint()
    assert h.cell == cell and h.value is None


def test_error_cells_from_rules(puzzle):
    s = GameSession(puzzle)
    s.board = [[None] * 6 for _ in range(6)]
    s.board[0][0] = s.board[0][1] = s.board[0][2] = HILAL
    assert {(0, 0), (0, 1), (0, 2)} <= s.error_cells()


def test_shapes_are_distinct_polygons():
    cres = crescent_points(50, 50, 20)
    star = star_points(50, 50, 20)
    assert len(star) == 20 and len(cres) > 40
    xs, ys = cres[0::2], cres[1::2]
    assert all(math.isfinite(v) for v in cres)
    assert max(ys) - min(ys) == pytest.approx(40, abs=0.5)  # dış çap
    # Hilalin ortası boş: merkezin sağındaki nokta içeride olmamalı (açıklık sağda)
    assert max(xs) < 50 + 0.12 * 20 + 20 + 1e-6


def test_theme_calendar():
    assert theme_for(date(2026, 11, 10)) is TEN_NOVEMBER
    assert theme_for(date(2027, 11, 10)) is TEN_NOVEMBER
    assert theme_for(date(2026, 11, 11)) is DEFAULT
    assert DEFAULT.hilal_color == TEN_NOVEMBER.hilal_color == "#FFFFFF"
    assert DEFAULT.yildiz_color == TEN_NOVEMBER.yildiz_color == "#E30A17"
    assert DEFAULT.bg == TEN_NOVEMBER.bg == "#000000"
    assert DEFAULT.title == TEN_NOVEMBER.title == "10 Kasım"
    assert DEFAULT.dates_line == TEN_NOVEMBER.dates_line == "1881 – 1938"
    assert DEFAULT.horizontal_eight and TEN_NOVEMBER.horizontal_eight
    t = TEN_NOVEMBER
    assert t.accent.upper() == "#E30A17" and not t.celebrate
    assert t.error_color != t.yildiz_color


def test_board_size_subtitle_changes_with_selected_size():
    from ui.app import size_subtitle
    assert size_subtitle(DEFAULT, 4) == "Her satır ve sütunda 2 hilal, 2 yıldız."
    assert size_subtitle(DEFAULT, 6) == "Her satır ve sütunda 3 hilal, 3 yıldız."
    assert size_subtitle(DEFAULT, 8) == "Her satır ve sütunda 4 hilal, 4 yıldız."
    assert size_subtitle(TEN_NOVEMBER, 4).endswith("Her satır ve sütunda 2 hilal, 2 yıldız.")


def test_stats_streak(tmp_path):
    st = StatsStore(tmp_path / "s.json")
    for day in (8, 9, 10):
        assert st.record_daily(date(2026, 11, day), 100, 20, 1, 0)
    assert not st.record_daily(date(2026, 11, 10), 5, 5, 0, 0)  # ilk sonuç korunur
    assert st.streak(date(2026, 11, 10)) == 3
    assert st.streak(date(2026, 11, 11)) == 3   # bugün henüz çözülmedi, seri sürüyor
    assert st.streak(date(2026, 11, 12)) == 0
    st.record_daily(date(2026, 11, 1), 1, 1, 0, 0)
    assert StatsStore(tmp_path / "s.json").best_streak() == 3


def test_stats_survives_corrupt_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{bozuk", encoding="utf-8")
    assert StatsStore(p).data == {"daily": {}}


def test_stats_paths_are_dimension_specific():
    assert StatsStore(n=4).path != StatsStore(n=6).path
    assert StatsStore(n=6).path != StatsStore(n=8).path


def test_puzzle_roundtrip_and_cache(tmp_path):
    p = generate(11, "orta")
    q = Puzzle.from_dict(json.loads(json.dumps(p.to_dict())))
    assert q.fingerprint == p.fingerprint and q.solution == p.solution and q.tier == p.tier
    d = date(2026, 11, 11)
    a = puzzle_for(d, cache_dir=tmp_path)
    assert (tmp_path / "2026-11-11.json").exists()
    b = puzzle_for(d, cache_dir=tmp_path)
    assert a.fingerprint == b.fingerprint
    (tmp_path / "2026-11-11.json").write_text("bozuk", encoding="utf-8")
    assert puzzle_for(d, cache_dir=tmp_path).fingerprint == a.fingerprint


def test_random_puzzles_are_medium_plus_and_differ():
    from game.daily import PLAY_TIERS, random_puzzle
    ps = [random_puzzle() for _ in range(5)]
    assert len({p.fingerprint for p in ps}) == 5
    assert all(p.tier in PLAY_TIERS for p in ps)


def test_pool_never_repeats_and_refills(tmp_path):
    from game.daily import PLAY_TIERS, PuzzlePool, fingerprint_key
    pool = PuzzlePool(tmp_path, size=2)
    assert pool.take() is None
    assert pool.refill() == 2 and len(pool.files()) == 2
    shown = [pool.next_puzzle() for _ in range(4)]  # 2 havuzdan, 2 hızlı yoldan
    keys = [fingerprint_key(p) for p in shown]
    assert len(set(keys)) == 4
    assert pool.history() == keys
    assert all(p.tier in PLAY_TIERS for p in shown)
    assert pool.files() == []
    # Geçmişteki bir bulmaca havuza düşse bile verilmez
    from game.daily import save_puzzle
    save_puzzle(pool.dir / "eski.json", shown[0])
    assert pool.take() is None


def test_screenshot_board_violations_are_reported():
    """Kullanıcının ekran görüntüsündeki hatalı tahta: üç ihlalin üçü de yakalanmalı."""
    from ui.app import violation_messages
    from game.rules import violations
    H, Y, _ = 0, 1, None
    b = [[_, _, _, _, _, H], [_, _, Y, H, _, Y], [_, _, _, H, Y, Y],
         [_, _, _, Y, _, H], [Y, _, _, Y, _, Y], [_, _, _, Y, _, Y]]
    links = {((1, 3), (2, 3)): "x", ((1, 5), (2, 5)): "=", ((1, 1), (2, 1)): "="}
    kinds = sorted(k for k, _ in violations(b, links))
    assert kinds == ["count", "sign", "triple"]
    msgs = violation_messages(b, links)
    assert "Yan yana ya da alt alta 3 aynı sembol olamaz." in msgs
    assert "Bir sütunda en fazla 3 yıldız olabilir." in msgs
    assert "× işaretli iki hücre farklı olmalı." in msgs


def test_four_by_four_violation_message_uses_dynamic_count():
    from ui.app import violation_messages
    board = [[None] * 4 for _ in range(4)]
    board[0][:3] = [1, 1, 1]
    assert "Bir satırda en fazla 2 yıldız olabilir." in violation_messages(board, {}, n=4)


def test_completion_is_rule_based(puzzle):
    """Dolu ve kurallara uyan tahta bitmiş sayılır; tek bir hata bile varsa bitmez."""
    s = GameSession(puzzle)
    sol = puzzle.solution
    free = [c for c in CELLS if c not in puzzle.givens]
    for r, c in free[:-1]:
        s.set((r, c), sol[r][c])
    assert not s.finished
    r, c = free[-1]
    s.set((r, c), 1 - sol[r][c])  # tahta dolu ama son hücre yanlış
    assert not s.finished and s.error_cells()
    s.set((r, c), sol[r][c])
    assert s.finished
