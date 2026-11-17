import statistics
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta

from game.daily import puzzle_for, seed_for, tier_for
from game.solver import count_solutions, solve

START = date(2026, 11, 10)


def test_same_date_same_puzzle():
    d = date(2026, 11, 10)
    assert seed_for(d) == seed_for(date(2026, 11, 10))
    assert puzzle_for(d).fingerprint == puzzle_for(d).fingerprint
    assert seed_for(d) != seed_for(d + timedelta(days=1))


def test_weekday_difficulty():
    assert tier_for(date(2026, 11, 9)) == "kolay"     # Pazartesi
    assert tier_for(date(2026, 11, 10)) == "kolay"    # Salı
    assert tier_for(date(2026, 11, 11)) == "orta"     # Çarşamba
    assert tier_for(date(2026, 11, 13)) == "zor"      # Cuma
    assert tier_for(date(2026, 11, 15)) == "çok zor"  # Pazar


def _one_day(offset: int):
    d = START + timedelta(days=offset)
    t = time.perf_counter()
    p = puzzle_for(d)
    elapsed = time.perf_counter() - t
    ok = count_solutions(p.givens, p.links) == 1 and solve(p.givens, p.links, p.level).solved
    return d, elapsed, p.fingerprint, p.tier, tier_for(d), bool(p.notes), ok, p.clue_count


def test_365_days_time_and_no_repeats():
    with ProcessPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(_one_day, range(365)))
    times = [r[1] for r in rows]
    fps = [r[2] for r in rows]
    by_tier = Counter(r[3] for r in rows)
    print(f"\n365 gün: toplam {sum(times):.1f} sn (tek çekirdek eşdeğeri), "
          f"ortalama {statistics.mean(times):.2f} sn, medyan {statistics.median(times):.2f} sn, "
          f"en uzun {max(times):.2f} sn ({max(rows, key=lambda r: r[1])[0]})")
    print(f"zorluk dağılımı: {dict(by_tier)}; ipucu ort. {statistics.mean(r[7] for r in rows):.1f} "
          f"(min {min(r[7] for r in rows)}, maks {max(r[7] for r in rows)})")
    assert len(set(fps)) == 365, "tekrar eden bulmaca var"
    assert all(r[6] for r in rows)
    assert all(r[3] == r[4] for r in rows), "hedef zorluk tutmayan gün var"
    assert not any(r[5] for r in rows)
    assert max(times) < 60
