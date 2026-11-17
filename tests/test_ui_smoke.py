"""tkinter arayüzünün açılıp tam bir oyunu bitirebildiğini doğrular (ekran yoksa atlanır)."""
import gc
import time
from datetime import date

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture(autouse=True)
def _collect_in_main_thread():
    """Kapatılan Tk nesneleri ana iş parçacığında toplansın. Arka plandaki üretim
    iş parçacığında toplanırlarsa Tcl süreci çökertir (yalnızca testte, aynı
    süreçte birden çok pencere açıldığı için)."""
    gc.collect()
    yield
    gc.collect()


def _wait(app, cond, timeout=60):
    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    return cond()


def _open(day, tmp_path, refill=False):
    from game.daily import PuzzlePool
    from ui.app import App
    for attempt in range(3):
        try:
            return App(day, pool=PuzzlePool(tmp_path, size=1), refill=refill)
        except tk.TclError as e:
            err = e
            gc.collect()
            time.sleep(0.2)
    pytest.skip(f"ekran yok: {err}")


def _outline_colors(app, cell):
    """Tuvalde verilen hücreyi kaplayan dikdörtgenlerin çerçeve renkleri."""
    x, y = app._xy(*cell)
    cv = app.canvas
    out = set()
    for i in cv.find_all():
        if cv.type(i) != "rectangle":
            continue
        x0, y0, x1, y1 = cv.coords(i)
        if x - 1 <= x0 and y - 1 <= y0 and x1 <= x + app.cell + 1 and y1 <= y + app.cell + 1:
            out.add(cv.itemcget(i, "outline"))
    return out


def _labels(widget):
    out = []
    for w in widget.winfo_children():
        if isinstance(w, (tk.Label, tk.Button)):
            out.append(w.cget("text"))
        out += _labels(w)
    return out


def _find_label(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and child.cget("text") == text:
            return child
        found = _find_label(child, text)
        if found is not None:
            return found
    return None


def _cell_symbols(app, cell):
    x, y = app._xy(*cell)
    cv = app.canvas
    return [
        item for item in cv.find_all()
        if cv.type(item) == "polygon"
        and all(x <= px <= x + app.cell and y <= py <= y + app.cell
                for px, py in zip(cv.coords(item)[::2], cv.coords(item)[1::2]))
    ]


def test_app_plays_full_game(tmp_path):
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        assert app.lbl_title.cget("text") == "10 Kasım"
        texts = _labels(app)
        assert {"Geri al", "İpucu", "Temizle"} <= set(texts)
        for word in ("Yinele", "kolay", "orta", "zor", "Günlük", "Pratik"):
            assert not any(word in t for t in texts), word
        assert "Kurallar" in texts
        s = app.session
        r, c = next((r, c) for r in range(6) for c in range(6) if (r, c) not in s.puzzle.givens)
        x, y = app._xy(r, c)
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), 1)
        assert s.value((r, c)) == 0
        symbol = _cell_symbols(app, (r, c))[-1]
        assert app.canvas.itemcget(symbol, "fill") == "#FFFFFF"
        assert app.canvas.itemcget(symbol, "outline") == "#FFFFFF"
        assert app.canvas.itemcget(symbol, "stipple") == ""
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), 1)
        assert s.value((r, c)) == 1
        symbol = _cell_symbols(app, (r, c))[-1]
        assert app.canvas.itemcget(symbol, "fill") == "#E30A17"
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), 1)
        assert s.value((r, c)) is None
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), -1)
        assert s.value((r, c)) == 1
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), -1)
        assert s.value((r, c)) is None
        app._click(type("E", (), {"x": x + 5, "y": y + 5})(), -1)
        assert s.value((r, c)) == 1
        app.undo()
        assert s.value((r, c)) is None
        for r, c in ((r, c) for r in range(6) for c in range(6)):
            app.cursor = (r, c)
            app._set_at_cursor(s.puzzle.solution[r][c])
        assert s.finished
        assert _wait(app, lambda: app._result_win is not None, timeout=5)
        assert app.lbl_error.cget("text") == ""
    finally:
        app.destroy()


def _place_triple(app):
    """Bir satıra yan yana üç hilal koyar (sabit hücrelerle çakışmayan yere). Üçlüyü döner."""
    s = app.session
    for r in range(6):
        for c0 in range(4):
            trio = [(r, c0 + i) for i in range(3)]
            if {s.puzzle.givens.get(x) for x in trio} - {None} <= {0}:
                for x in trio:
                    if x not in s.puzzle.givens:
                        app.cursor = x
                        app._set_at_cursor(0)
                return trio
    pytest.fail("uygun satır bulunamadı")


def test_error_warning_waits_two_seconds(tmp_path):
    from ui.app import ERROR_DELAY_MS
    assert ERROR_DELAY_MS == 2000
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        app.update()  # ilk çizimi bitir; zamanlama ölçümünü etkilemesin
        app.error_delay_ms = 1200  # testi hızlandırmak için; davranış aynı
        t0 = time.time()
        trio = _place_triple(app)
        app.update()
        # Hemen gösterilmez
        assert app.lbl_error.cget("text") == ""
        # Ekranda en fazla 2 mesaj gösterilir; üçlü bazen 3. mesaj olabildiği için
        # herhangi bir uyarının çıkması ve üçlünün işaretlenmesi beklenir.
        assert _wait(app, lambda: app.lbl_error.cget("text") != "", timeout=5)
        assert set(trio) <= {c for k, cells in app._revealed for c in cells}
        assert time.time() - t0 >= 1.1
        # Düzeltince beklemeden kaybolur
        last = next(x for x in reversed(trio) if x not in app.session.puzzle.givens)
        app.cursor = last
        app._set_at_cursor(None)
        app.update()
        assert app.lbl_error.cget("text") == ""
    finally:
        app.destroy()


def test_quick_cycling_does_not_flash_errors(tmp_path):
    """Aynı hücreye arka arkaya tıklarken ara durumlar uyarı vermemeli (süre baştan başlar)."""
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        app.error_delay_ms = 400
        trio = _place_triple(app)
        last = next(x for x in reversed(trio) if x not in app.session.puzzle.givens)
        app.cursor = last
        for _ in range(4):  # her 0,25 sn'de bir hamle: süre hiç dolmaz
            t = time.time() + 0.25
            while time.time() < t:
                app.update()
                time.sleep(0.02)
            app._cycle_at_cursor()
        app.update()
        assert app.lbl_error.cget("text") == ""
    finally:
        app.destroy()


@pytest.mark.parametrize("fullscreen", [False, True])
def test_solving_by_clicks_shows_result_over_board(tmp_path, fullscreen):
    """Oyuncu gibi fareyle çöz: sonuç pencerenin içinde, tahtanın ortasında görünmeli."""
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        if fullscreen:
            app.toggle_fullscreen()
        for _ in range(10):
            app.update()
            time.sleep(0.02)
        s = app.session
        for r in range(6):
            for c in range(6):
                if (r, c) in s.puzzle.givens:
                    continue
                x, y = app._xy(r, c)
                ev = type("E", (), {"x": x + app.cell / 2, "y": y + app.cell / 2})()
                for _ in range(1 if s.puzzle.solution[r][c] == 0 else 2):  # hilal 1, yıldız 2 tık
                    app._click(ev, 1)
        assert s.finished
        assert _wait(app, lambda: app._result_win is not None, timeout=5)
        app.update()
        win = app._result_win
        assert win is not None and win.winfo_ismapped() and win.winfo_toplevel() is app
        texts = _labels(win)
        assert "Bulmaca tamamlandı." in texts and "Yeni bulmaca" in texts
        # Sonuç kutusunun ortası tuvalin ortasında
        wx = win.winfo_rootx() + win.winfo_width() / 2
        cx = app.canvas.winfo_rootx() + app.canvas.winfo_width() / 2
        assert abs(wx - cx) < 3
        assert app.lbl_error.cget("text") == ""
    finally:
        app.destroy()


def test_each_launch_gets_a_different_puzzle(tmp_path):
    seen = set()
    for _ in range(3):
        app = _open(date(2026, 11, 11), tmp_path)
        try:
            assert _wait(app, lambda: app.session is not None)
            seen.add(app.session.puzzle.fingerprint)
        finally:
            app.destroy()
            del app
            gc.collect()
    assert len(seen) == 3


def test_board_scales_with_window_and_fullscreen(tmp_path):
    app = _open(date(2026, 11, 11), tmp_path)
    try:
        app.geometry("500x650")
        _wait(app, lambda: app.winfo_height() == 650, timeout=5)
        small = app.cell
        app.geometry("700x800")
        _wait(app, lambda: app.cell > small * 1.3, timeout=5)
        assert app.cell > small * 1.3
        app.toggle_fullscreen()
        app.update()
        assert app.fullscreen and app.attributes("-fullscreen")
        app.set_fullscreen(False)
        app.update()
        assert not app.attributes("-fullscreen")
    finally:
        app.destroy()


def test_hint_teaches_a_forced_move_and_does_not_fill(tmp_path):
    """İpucu: rastgele değil, çözücünün zorunlu hamlesi; yalnızca kutuyu belirtir (metin
    yazmaz), hücreyi kendisi doldurmaz."""
    from game.solver import TECHNIQUE_LEVELS
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        s = app.session
        before = [row[:] for row in s.board]
        app.show_hint()
        h = app.hint
        assert h is not None and h.move is not None
        assert s.board == before                       # tahtaya yazmaz
        assert s.value(h.cell) is None                 # boş bir hücreyi gösterir
        assert h.value == s.puzzle.solution[h.cell[0]][h.cell[1]]   # doğru (zorunlu) değer
        assert h.move.technique in TECHNIQUE_LEVELS
        assert app.lbl_error.cget("text") == ""            # ipucu metni yazılmaz
        assert _outline_colors(app, h.cell) & {app.theme.hint_color}
        # Başlangıçta en basit teknik kullanılır (kalite filtresi: ilk hamle seviye <= 3)
        assert h.move.level <= 3
        # Gerekçe hücreleri dolu hücrelerdir (kural onlara dayanır)
        assert all(s.value(c) is not None for c in h.move.because)
        assert s.hints == 1
        # Oyuncu hamleyi yapınca ipucu kalkar
        app.cursor = h.cell
        app._set_at_cursor(h.value)
        assert app.hint is None
    finally:
        app.destroy()


def test_hints_alone_finish_the_puzzle(tmp_path):
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        app.pulse_ms = 200
        s = app.session
        for _ in range(40):
            if s.finished:
                break
            app.show_hint()
            h = app.hint
            app.cursor = h.cell
            app._set_at_cursor(h.value)
        assert s.finished and s.hints > 0
        assert _wait(app, lambda: app._result_win is not None, timeout=5)
        assert "İpucu" in _labels(app._result_win)
    finally:
        app.destroy()


def test_hint_points_out_wrong_cell_first(tmp_path):
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        s = app.session
        cell = next(c for c in ((r, c) for r in range(6) for c in range(6))
                    if c not in s.puzzle.givens)
        app.cursor = cell
        app._set_at_cursor(1 - s.puzzle.solution[cell[0]][cell[1]])
        app.show_hint()
        assert app.hint.cell == cell and app.hint.value is None
        assert app.lbl_error.cget("text") == ""            # metin yok
        assert app.theme.error_color in _outline_colors(app, cell)   # yanlış kutu hata renginde
    finally:
        app.destroy()


def test_completion_pulse_is_subtle_and_ends(tmp_path):
    from ui.app import PULSE_AMPLITUDE
    assert PULSE_AMPLITUDE <= 0.1
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert _wait(app, lambda: app.session is not None)
        app.pulse_ms = 600
        s = app.session
        for r in range(6):
            for c in range(6):
                app.cursor = (r, c)
                app._set_at_cursor(s.puzzle.solution[r][c])
        assert s.finished and app._result_win is None   # önce dalga, sonra sonuç
        seen = []
        while app._result_win is None:
            app.update()
            seen += [app.pulse_scale(r, c) for r in range(6) for c in range(6)]
            time.sleep(0.01)
        assert max(seen) > 1.02                         # gerçekten büyüdü
        assert max(seen) <= 1 + PULSE_AMPLITUDE + 1e-9  # ama çok az
        assert min(seen) >= 1.0                         # hiç küçülmez (normale döner)
        assert all(app.pulse_scale(r, c) == 1.0 for r in range(6) for c in range(6))
    finally:
        app.destroy()


def test_ten_november_touches_and_default_theme(tmp_path):
    from themes.calendar import DEFAULT, TEN_NOVEMBER
    app = _open(date(2026, 11, 10), tmp_path)
    try:
        assert hasattr(app, "emblem")
        assert app.lbl_title.cget("text") == "10 Kasım"
        cv = app.dates_canvas
        texts = [cv.itemcget(item, "text") for item in cv.find_all() if cv.type(item) == "text"]
        assert texts == ["1881 – 193"]
        assert cv.date_text == "1881 – 1938"
        images = [item for item in cv.find_all() if cv.type(item) == "image"]
        assert len(images) == 1 and cv.horizontal_eight_image is not None
        x0, y0, x1, y1 = cv.horizontal_eight_bbox
        assert (x1 - x0) > (y1 - y0)
        app._show_start_screen()
        assert "10 Kasım" in _labels(app._menu_frame)
        assert app.start_dates_canvas.date_text == "1881 – 1938"
        assert len([item for item in app.start_dates_canvas.find_all()
                    if app.start_dates_canvas.type(item) == "image"]) == 1
    finally:
        app.destroy()

    app = _open(date(2026, 11, 11), tmp_path)
    try:
        assert not hasattr(app, "emblem") and hasattr(app, "dates_canvas")
        assert app.lbl_title.cget("text") == "10 Kasım"
        assert app.dates_canvas.date_text == "1881 – 1938"
        assert "Kurallar" in _labels(app)
        app.update()
        center = app.winfo_rootx() + app.winfo_width() / 2
        title = _find_label(app.rules_box, "Kurallar")
        footer = _find_label(app.rules_box, "Her bulmacanın tek bir doğru çözümü vardır ve mantıkla çözülür.")
        assert title is not None and abs(title.winfo_rootx() + title.winfo_width() / 2 - center) <= 2
        assert footer is not None and abs(footer.winfo_rootx() + footer.winfo_width() / 2 - center) <= 2
        fullscreen_hint = _find_label(app, "F11 · tam ekran")
        assert fullscreen_hint is not None
        assert app.rules_box.winfo_rooty() > fullscreen_hint.winfo_rooty()
    finally:
        app.destroy()
    assert DEFAULT.top_band is None and not DEFAULT.emblem
    assert TEN_NOVEMBER.top_band.upper() == "#E30A17" and not TEN_NOVEMBER.celebrate
