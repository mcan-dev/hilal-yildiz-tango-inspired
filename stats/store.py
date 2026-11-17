"""JSON istatistik deposu: süre, hamle, geri alma, ipucu, seri (streak).

Yalnızca günlük resmi bulmacalar seriye sayılır. Bir günün ilk tamamlanışı kaydedilir.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path


def default_dir() -> Path:
    base = os.environ.get("HILAL_YILDIZ_HOME")
    return Path(base) if base else Path.home() / ".hilal_yildiz"


class StatsStore:
    """Keep daily results in a dimension-specific JSON file."""

    def __init__(self, path: Path | None = None, n: int = 6):
        """Select the compatible legacy 6x6 path or a separate size path."""
        if n not in (4, 6, 8):
            raise ValueError("tahta boyutu 4, 6 veya 8 olmalı")
        filename = "stats.json" if n == 6 else f"stats-{n}.json"
        self.path = Path(path) if path else default_dir() / filename
        self.data = self._load()

    def _load(self) -> dict:
        """Read valid stored JSON or start with an empty daily history."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("daily"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"daily": {}}

    def save(self) -> None:
        """Persist the current statistics atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def result_for(self, d: date) -> dict | None:
        """Return the stored result for a date, if one exists."""
        return self.data["daily"].get(d.isoformat())

    def record_daily(self, d: date, seconds: int, moves: int, undos: int, hints: int) -> bool:
        """Günün sonucunu kaydeder. Gün zaten kayıtlıysa False döner ve değiştirmez."""
        key = d.isoformat()
        if key in self.data["daily"]:
            return False
        self.data["daily"][key] = {"seconds": seconds, "moves": moves, "undos": undos, "hints": hints}
        self.save()
        return True

    def streak(self, today: date) -> int:
        """Bugünden (bugün henüz çözülmediyse dünden) geriye kesintisiz çözülen gün sayısı."""
        days = self.data["daily"]
        d = today if today.isoformat() in days else today - timedelta(days=1)
        n = 0
        while d.isoformat() in days:
            n += 1
            d -= timedelta(days=1)
        return n

    def best_streak(self) -> int:
        """Return the longest consecutive run in the recorded dates."""
        dates = sorted(date.fromisoformat(k) for k in self.data["daily"])
        best = cur = 0
        prev = None
        for d in dates:
            cur = cur + 1 if prev and d - prev == timedelta(days=1) else 1
            best = max(best, cur)
            prev = d
        return best
