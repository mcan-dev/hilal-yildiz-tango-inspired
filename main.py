"""Hilal & Yıldız giriş noktası.

    python main.py                    # arayüz, bugünün bulmacası
    python main.py --date 2026-11-10  # belirli bir günün bulmacası ve teması
    python main.py --text             # arayüzsüz, bulmacayı metin olarak bas
"""
import argparse
from datetime import date

from game.daily import get_daily_puzzle, tier_for


def print_text(d: date, n: int = 6) -> None:
    """Print the selected day's puzzle in a compact text board."""
    p = get_daily_puzzle(d, n)
    print(f"{d.isoformat()} — zorluk: {tier_for(d)} — {len(p.givens)} sembol, {len(p.links)} işaret")
    sym = {0: "☾", 1: "★", None: "·"}
    for r in range(n):
        print(" ".join(sym[p.givens.get((r, c))] for c in range(n)))
    for (a, b), t in sorted(p.links.items()):
        print(f"  {a} {'=' if t == '=' else '×'} {b}")


def main() -> None:
    """Parse command-line options and start the UI or text view."""
    ap = argparse.ArgumentParser(description="Hilal & Yıldız")
    ap.add_argument("--date", type=date.fromisoformat, default=None, help="YYYY-AA-GG")
    ap.add_argument("--text", action="store_true", help="arayüz olmadan metin çıktısı")
    ap.add_argument("--size", type=int, choices=(4, 6, 8), default=6, help="tahta boyutu")
    args = ap.parse_args()
    d = args.date or date.today()
    if args.text:
        print_text(d, args.size)
    else:
        from ui.app import run
        run(d)


if __name__ == "__main__":
    main()
