"""tkinter arayüzü. Hilal ve yıldız Canvas üzerinde çokgen olarak çizilir.

Her açılışta farklı bir bulmaca gelir (en az orta zorlukta). Bekleme olmasın diye
birkaç bulmaca arka planda hazırlanıp diskte bekletilir; gösterilen bulmacalar
bir daha verilmez. Kural ihlalleri (üçlü, sayı aşımı, = / × işareti) iki saniye
sonra taranarak gösterilir ve altta hangi kuralın bozulduğu yazar.

İpucu butonu rastgele bir hücre açmaz: çözücünün bulduğu bir sonraki ZORUNLU
hamleyi, en basit teknikle ve hangi kurala dayandığıyla gösterir; gerekçe
hücreleri vurgulanır, hamleyi oyuncu yapar. Bulmaca bitince semboller dalga
hâlinde çok hafif büyüyüp küçülür, ardından sonuç gösterilir.

Fare:    sol tık  boş -> hilal -> yıldız -> boş,  sağ tık ters yön
Klavye:  oklar imleç,  1 hilal,  2 yıldız,  boşluk döngü,  0/Del/Backspace sil,
         Ctrl+Z geri al,  Ctrl+Y yinele,  F11 tam ekran,  Esc tam ekrandan çık
"""
from __future__ import annotations

import math
import os
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont, ImageTk

from game.daily import PuzzlePool, get_daily_puzzle
from game.generator import Puzzle
from game.rules import HILAL, N, SAME, SYMBOL_NAMES, YILDIZ, geometry, violations
from game.session import GameSession
from stats.store import StatsStore, default_dir
from themes.calendar import theme_for

from .shapes import crescent_points, star_points

FONT = "Segoe UI"
HILAL_COLOR = "#FFFFFF"
YILDIZ_COLOR = "#E30A17"
ERROR_DELAY_MS = 2000
PULSE_MS = 1400          # bitiş dalgasının toplam süresi
PULSE_AMPLITUDE = 0.08   # sembollerin en fazla büyüme oranı (%8, çok hafif)

RULES = (
    ("pair", ""),
    ("two", "Yan yana ya da alt alta en fazla 2 aynı sembol gelebilir."),
    ("same", "= ile bağlı iki hücre aynı sembolü alır."),
    ("diff", "× ile bağlı iki hücre farklı sembol alır."),
)
RULES_FOOTER = "Her bulmacanın tek bir doğru çözümü vardır ve mantıkla çözülür."


# Seçilen tahta boyutuna göre başlık altındaki kural açıklamasını hazırlar.
def size_subtitle(theme, n: int) -> str:
    count_text = f"Her satır ve sütunda {n // 2} hilal, {n // 2} yıldız."
    if theme.key == "default":
        return count_text
    return f"{theme.subtitle}\n{count_text}"


# Süreyi arayüzde kısa ve sabit genişlikte göstermek için kullanılır.
def fmt_time(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


# Kural ihlallerini oyuncunun anlayacağı kısa uyarılara dönüştürür.
def violation_messages(board, links, found=None, n: int = N) -> list[str]:
    """Tahtadaki ihlallerin oyuncuya gösterilecek açıklamaları (tekrarsız, sıralı)."""
    out: list[str] = []
    for kind, cells in (violations(board, links, n=n) if found is None else found):
        if kind == "triple":
            msg = "Yan yana ya da alt alta 3 aynı sembol olamaz."
        elif kind == "count":
            r, c = cells[0]
            sym = SYMBOL_NAMES[board[r][c]]
            line = "satırda" if all(x[0] == r for x in cells) else "sütunda"
            msg = f"Bir {line} en fazla {n // 2} {sym} olabilir."
        else:
            a, b = cells
            key = (a, b) if (a, b) in links else (b, a)
            msg = ("= işaretli iki hücre aynı olmalı." if links[key] == SAME
                   else "× işaretli iki hücre farklı olmalı.")
        if msg not in out:
            out.append(msg)
    return out


# Oyunun ana penceresini ve kullanıcı etkileşimlerini yönetir.
class App(tk.Tk):
    # Tema, bulmaca ve Tk kontrollerini tek oyun penceresinde başlatır.
    def __init__(self, day: date | None = None, pool: PuzzlePool | None = None,
                 refill: bool = True, n: int = N, start_screen: bool = False):
        super().__init__()
        self.n = n
        self.cells, self.lines, self.edges = geometry(n)
        if n not in (4, 6, 8):
            raise ValueError("tahta boyutu 4, 6 veya 8 olmalı")
        self.start_screen = start_screen
        self.daily_mode = start_screen
        self.day = day or date.today()
        self.theme = theme_for(self.day)
        self.pool = pool or PuzzlePool(default_dir())
        self.refill = refill
        self.session: GameSession | None = None
        self.cursor = (0, 0)
        self._jobs: queue.Queue = queue.Queue()
        self._job_token = 0
        self._refilling = threading.Event()
        self._result_win: tk.Frame | None = None
        self.fullscreen = False
        # Hata uyarısı gecikmesi: yeni bir ihlal, son hamleden bu kadar sonra görünür.
        # Her hamlede süre baştan başlar (hücreye arka arkaya tıklarken ara
        # durumlar yanıp sönmesin). Düzeltilen ihlal ise hemen kaybolur.
        self.error_delay_ms = ERROR_DELAY_MS
        self._revealed: set = set()
        self._reveal_job: str | None = None
        self.hint = None                  # gösterilen ipucu (game.session.Hint)
        self.pulse_ms = PULSE_MS
        self._pulse_t: float | None = None  # bitiş dalgasında geçen süre (sn)
        self._pulse_job: str | None = None

        self.scale = self.winfo_fpixels("1i") / 96.0
        # Çizim ölçüleri tuval boyutuna göre her çizimde yeniden hesaplanır.
        self.cell = 80.0
        self.ox = self.oy = 0.0

        self.title(f"Hilal & Yıldız — {self.theme.title}")
        self.configure(bg=self.theme.bg)
        # Geniş pencere, ama ekrana sığsın (görev çubuğu payı bırakılır).
        h = min(int(860 * self.scale), self.winfo_screenheight() - int(90 * self.scale))
        w = min(int(680 * self.scale), self.winfo_screenwidth() - 40)
        y = max((self.winfo_screenheight() - h) // 2 - int(30 * self.scale), 0)
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{y}")
        self.minsize(int(420 * self.scale), int(600 * self.scale))
        self._build()
        self._bind_keys()
        if start_screen:
            self._show_start_screen()
        else:
            self.new_puzzle()
        self._tick()

    # ------------------------------------------------------------------ yapı
    # Pencerenin başlık, kontroller ve oyun tahtası bölümlerini kurar.
    def _build(self) -> None:
        t = self.theme
        pad = {"padx": 20}
        if t.top_band:
            tk.Frame(self, bg=t.top_band, height=max(3, int(4 * self.scale))).pack(fill="x")
        head = tk.Frame(self, bg=t.bg)
        head.pack(pady=(14 if t.top_band else 18, 0), **pad)
        if t.emblem:
            self.emblem = self._make_emblem(head, int(26 * self.scale))
            self.emblem.pack(side="left", padx=(0, 12))
        self.lbl_title = tk.Label(head, text=t.title, font=(FONT, 24, "bold"), bg=t.bg, fg=t.text)
        self.lbl_title.pack(side="left")
        self.lbl_sub = tk.Label(self, text=size_subtitle(t, self.n), font=(FONT, 11), bg=t.bg, fg=t.text_muted,
                                wraplength=int(560 * self.scale))
        self.lbl_sub.pack(**pad)
        if t.dates_line:
            if t.horizontal_eight and t.dates_line.endswith("8"):
                self.dates_canvas = self._make_horizontal_eight(t.dates_line)
                self.dates_canvas.pack(pady=(2, 0))
            else:
                tk.Label(self, text=t.dates_line, font=(FONT, 10), bg=t.bg,
                         fg=t.text_muted).pack(pady=(2, 0))
        tk.Frame(self, bg=t.accent, height=2, width=70).pack(pady=(8, 6))

        info = tk.Frame(self, bg=t.bg)
        info.pack(fill="x", **pad)
        self.lbl_timer = tk.Label(info, text="0:00", font=(FONT, 14, "bold"), bg=t.bg, fg=t.text)
        self.lbl_timer.pack(side="right")

        # Sessiz dakika satırı yalnızca o dakika görünür (bkz. _tick).
        self.lbl_silent = tk.Label(self, text=t.silent_message, font=(FONT, 11, "italic"),
                                   bg=t.bg, fg=t.text_muted)

        # Alt kısımlar önce yerleşir ki tuval kalan tüm alanı alsın.
        self._build_rules()
        tk.Label(self, text="F11 · tam ekran", font=(FONT, 9), bg=t.bg,
                 fg=t.text_muted).pack(side="bottom", pady=(0, 8))
        bar = tk.Frame(self, bg=t.bg)
        bar.pack(side="bottom", pady=(4, 6))
        self.btn_undo = self._button(bar, "Geri al", self.undo)
        self.btn_hint = self._button(bar, "İpucu", self.show_hint)
        self.btn_clear = self._button(bar, "Temizle", self.clear)
        self.btn_size = self._button(bar, "Boyut değiştir", self._show_start_screen)
        self.lbl_error = tk.Label(self, text="", font=(FONT, 11), bg=t.bg, fg=t.error_color,
                                  justify="center", height=2, wraplength=int(600 * self.scale))
        self.lbl_error.pack(side="bottom", **pad)

        self.canvas = tk.Canvas(self, bg=t.bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(6, 0))
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", lambda e: self._click(e, 1))
        self.canvas.bind("<Button-3>", lambda e: self._click(e, -1))
        self._menu_frame = None

    # Başlangıç ve oyun sırasında boyut seçilebilmesini sağlar.
    def _show_start_screen(self) -> None:
        self._job_token += 1
        self._close_result()
        self._cancel_pulse()
        self.session = None
        self.daily_mode = True
        self.redraw()
        if self._menu_frame is not None:
            self._menu_frame.destroy()
        t = self.theme
        menu = tk.Frame(self, bg=t.bg)
        menu.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._menu_frame = menu
        heading = tk.Frame(menu, bg=t.bg)
        heading.pack(pady=(90, 0))
        if t.emblem:
            self.start_emblem = self._make_emblem(heading, int(26 * self.scale))
            self.start_emblem.pack(side="left", padx=(0, 12))
        tk.Label(heading, text=t.title, font=(FONT, 24, "bold"), bg=t.bg,
                 fg=t.text).pack(side="left")
        if t.dates_line:
            if t.horizontal_eight and t.dates_line.endswith("8"):
                self.start_dates_canvas = self._make_horizontal_eight(t.dates_line, menu)
                self.start_dates_canvas.pack(pady=(2, 0))
            else:
                tk.Label(menu, text=t.dates_line, font=(FONT, 10), bg=t.bg,
                         fg=t.text_muted).pack(pady=(2, 0))
        tk.Label(menu, text="Tahta boyutunu seçin", font=(FONT, 14), bg=t.bg,
                 fg=t.text_muted).pack(pady=(12, 20))
        for size in (4, 6, 8):
            tk.Button(
                menu, text=f"{size} × {size}", command=lambda size=size: self._select_size(size),
                font=(FONT, 16, "bold"), bg=t.panel, fg=t.text, activebackground=t.cell_fixed,
                relief="flat", padx=35, pady=14, cursor="hand2",
            ).pack(pady=8)

    # Seçilen boyutun günlük bulmacasını arka planda veritabanından yükler/üretir.
    def _select_size(self, n: int) -> None:
        self.n = n
        self.cells, self.lines, self.edges = geometry(n)
        self.lbl_sub.config(text=size_subtitle(self.theme, n))
        self.cursor = (0, 0)
        self.session = None
        self._close_result()
        self._cancel_pulse()
        self.hint = None
        if self._menu_frame is not None:
            self._menu_frame.destroy()
        self._menu_frame = None
        self.rules_box.destroy()
        self._build_rules()
        self.redraw()
        self._job_token += 1
        token = self._job_token
        jobs, day, size = self._jobs, self.day, n

        def load():
            try:
                jobs.put((token, get_daily_puzzle(day, size)))
            except Exception as exc:
                jobs.put((token, exc))

        threading.Thread(target=load, daemon=True).start()
        self.after(50, self._poll_job)

    # Kuralları oyun sırasında görünür ve erişilebilir tutar.
    def _build_rules(self) -> None:
        """Tango'daki gibi altta kısa kurallar: 2x2 düzen, her kuralın yanında çizimli simge."""
        t = self.theme
        box = tk.Frame(self, bg=t.bg)
        box.pack(side="bottom", fill="x", padx=24, pady=(2, 4))
        tk.Frame(box, bg=t.grid_line, height=1).pack(fill="x", pady=(0, 5))
        tk.Label(box, text="Kurallar", font=(FONT, 10, "bold"), bg=t.bg,
                 fg=t.text).pack(anchor="center")
        grid = tk.Frame(box, bg=t.bg)
        grid.pack(anchor="center")
        half = self.n // 2
        texts = (
            f"Her satır ve sütunda {half} hilal ve {half} yıldız olur.",
            RULES[1][1],
            RULES[2][1],
            RULES[3][1],
        )
        for i, ((icon, _), text) in enumerate(zip(RULES, texts)):
            cell = tk.Frame(grid, bg=t.bg)
            cell.grid(row=i // 2, column=i % 2, padx=8, pady=1, sticky="w")
            self._rule_icon(cell, icon).pack(side="left", padx=(0, 8))
            tk.Label(cell, text=text, font=(FONT, 9), bg=t.bg, fg=t.text_muted, justify="left",
                     wraplength=int(250 * self.scale)).pack(side="left")
        tk.Label(box, text=RULES_FOOTER, font=(FONT, 9, "italic"), bg=t.bg,
                 fg=t.text_muted).pack(anchor="center", pady=(3, 0))
        self.rules_box = box

    # Kural açıklamasına uygun küçük sembolü çizer.
    def _rule_icon(self, parent, kind: str) -> tk.Canvas:
        t, sc = self.theme, self.scale
        w, h = int(44 * sc), int(22 * sc)
        cv = tk.Canvas(parent, width=w, height=h, bg=t.bg, highlightthickness=0)
        R = h * 0.36
        if kind == "pair":
            cv.create_polygon(crescent_points(w * 0.25, h / 2, R), fill=HILAL_COLOR,
                              outline=t.grid_line, width=max(1, self.scale), stipple="")
            cv.create_polygon(star_points(w * 0.72, h / 2, R * 1.1), fill=YILDIZ_COLOR, outline="")
        elif kind == "two":
            for x in (w * 0.25, w * 0.70):
                cv.create_polygon(star_points(x, h / 2, R * 1.1), fill=YILDIZ_COLOR, outline="")
        else:
            cx, cy, rad = w / 2, h / 2, h * 0.38
            cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=t.sign_bg,
                           outline=t.sign_color)
            k, lw = rad * 0.5, max(2, int(2 * sc))
            if kind == "same":
                for dy in (-k * 0.55, k * 0.55):
                    cv.create_line(cx - k, cy + dy, cx + k, cy + dy, fill=t.sign_color, width=lw)
            else:
                cv.create_line(cx - k, cy - k, cx + k, cy + k, fill=t.sign_color, width=lw)
                cv.create_line(cx - k, cy + k, cx + k, cy - k, fill=t.sign_color, width=lw)
        return cv

    # 10 Kasım temasında başlığın yanında bayrak amblemi çizer.
    def _make_emblem(self, parent, g: int) -> tk.Canvas:
        """Bayrak amblemi (font değil, çizim). Oranlar Türk bayrağından: yükseklik G,
        hilal dış çapı G/2 ve merkezi gönderden G/2, yıldız çapı G/4."""
        t = self.theme
        w = int(g * 1.5)
        cv = tk.Canvas(parent, width=w, height=g, bg=t.bg, highlightthickness=0)
        red = t.top_band or t.accent
        cv.create_rectangle(0, 0, w, g, fill=red, outline="")
        R = 0.25 * g
        # crescent_points hilali 0,12R sağa kaydırır; bayrak ölçüsü için geri al.
        cv.create_polygon(crescent_points(0.5 * g - 0.12 * R, g / 2, R), fill="#FFFFFF",
                          outline="")
        cv.create_polygon(star_points(1.02 * g, g / 2, 0.125 * g, inner_ratio=0.38,
                                      rotation=math.pi), fill="#FFFFFF", outline="")
        return cv

    # Tarih satırındaki son 8'i, aynı yazı tipine uyan yatay vektör glifle çizer.
    def _make_horizontal_eight(self, text: str, parent=None) -> tk.Canvas:
        t = self.theme
        fnt = tkfont.Font(family=FONT, size=10)
        head = text[:-1]
        text_width = fnt.measure(head)
        font_size = abs(int(fnt.actual("size")))
        dpi_scale = self.winfo_fpixels("1i") / 72
        supersample = 4
        font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
        glyph_font = ImageFont.truetype(str(font_path), max(1, round(font_size * dpi_scale)) * supersample)
        bounds = glyph_font.getbbox("8")
        margin = supersample * 2
        glyph = Image.new(
            "RGBA",
            (bounds[2] - bounds[0] + margin * 2, bounds[3] - bounds[1] + margin * 2),
            (0, 0, 0, 0),
        )
        ImageDraw.Draw(glyph).text(
            (margin - bounds[0], margin - bounds[1]),
            "8",
            font=glyph_font,
            fill=t.text_muted,
        )
        rotated = glyph.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
        rotated = rotated.resize(
            (max(1, round(rotated.width / supersample)),
             max(1, round(rotated.height / supersample))),
            Image.Resampling.LANCZOS,
        )
        image = ImageTk.PhotoImage(rotated)
        gap = max(1, int(self.scale))
        height = fnt.metrics("linespace")
        height = max(height, image.height() + 2)
        width = int(text_width + gap + image.width() + 2)
        cv = tk.Canvas(self if parent is None else parent, width=width, height=height,
                       bg=t.bg, highlightthickness=0)
        cv.create_text(0, height / 2, text=head, anchor="w", font=fnt, fill=t.text_muted)
        x = text_width + gap
        y = (height - image.height()) / 2
        cv.create_image(x, y, image=image, anchor="nw")
        cv.horizontal_eight_image = image
        cv.horizontal_eight_bbox = (x, y, x + image.width(), y + image.height())
        cv.head_text = head
        cv.date_text = text
        return cv

    # Aynı görünümdeki düğmeleri ortak ayarlarla oluşturur.
    def _button(self, parent, text, cmd) -> tk.Button:
        t = self.theme
        b = tk.Button(parent, text=text, command=cmd, font=(FONT, 11), bg=t.panel, fg=t.text,
                      activebackground=t.cell_fixed, activeforeground=t.text, relief="flat",
                      bd=0, padx=16, pady=6, cursor="hand2", disabledforeground=t.text_muted)
        b.pack(side="left", padx=5)
        return b

    # Klavye kısayollarını ilgili oyun komutlarına bağlar.
    def _bind_keys(self) -> None:
        for key, d in (("Up", (-1, 0)), ("Down", (1, 0)), ("Left", (0, -1)), ("Right", (0, 1))):
            self.bind(f"<{key}>", lambda e, d=d: self._move_cursor(*d))
        self.bind("1", lambda e: self._set_at_cursor(HILAL))
        self.bind("2", lambda e: self._set_at_cursor(YILDIZ))
        for k in ("0", "<Delete>", "<BackSpace>"):
            self.bind(k, lambda e: self._set_at_cursor(None))
        self.bind("<space>", lambda e: self._cycle_at_cursor())
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.set_fullscreen(False))

    # Tam ekran durumunu istenen değere getirir.
    def set_fullscreen(self, on: bool) -> None:
        self.fullscreen = on
        self.attributes("-fullscreen", on)

    # Tam ekran görünümünü açıp kapatır.
    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.fullscreen)

    # -------------------------------------------------------------- yükleme
    # Yeni bulmacayı arka planda hazırlatıp oturumu yeniler.
    def new_puzzle(self) -> None:
        """Havuzdan (yoksa hızlı yoldan) yeni bir bulmaca alır, arka planda."""
        if self.daily_mode:
            self._select_size(self.n)
            return
        self._close_result()
        self._cancel_pulse()
        self.hint = None
        self.session = None
        self.redraw()
        # İş parçacığı pencereye (self) referans tutmamalı: Tk nesnesi yanlış
        # iş parçacığında silinirse Python çöker.
        self._job_token += 1
        token = self._job_token
        pool, jobs = self.pool, self._jobs

        def load():
            try:
                jobs.put((token, pool.next_puzzle()))
            except Exception as exc:
                jobs.put((token, exc))

        threading.Thread(target=load, daemon=True).start()
        self.after(50, self._poll_job)

    # Arka plan iş parçacığından hazır bulmacayı alır.
    def _poll_job(self) -> None:
        try:
            puzzle = self._jobs.get_nowait()
        except queue.Empty:
            self.after(50, self._poll_job)
            return
        token, puzzle = puzzle
        if token != self._job_token:
            self.after(50, self._poll_job)
            return
        if isinstance(puzzle, Exception):
            self.lbl_error.config(text=f"Bulmaca yüklenemedi: {puzzle}")
            return
        self._start_session(puzzle)

    # Gelen bulmacayla yeni oyun oturumu kurar.
    def _start_session(self, puzzle: Puzzle) -> None:
        self.n = puzzle.n
        self.cells, self.lines, self.edges = geometry(self.n)
        self.session = GameSession(puzzle)
        self.cursor = (0, 0)
        self._cancel_reveal()
        self._revealed = set()
        self.hint = None
        self.redraw()
        if not self.daily_mode:
            self._refill_pool()

    # Sonraki bulmacalar için havuzu kullanıcı arayüzünü durdurmadan doldurur.
    def _refill_pool(self) -> None:
        """Sonraki açılışlar için havuzu arka planda doldurur."""
        if not self.refill or self._refilling.is_set():
            return
        busy, pool = self._refilling, self.pool
        busy.set()

        # Havuzu doldurur; Tk arayüzüne iş parçacığından dokunmaz.
        def work():  # self'e dokunmaz (bkz. new_puzzle)
            try:
                pool.refill()
            finally:
                busy.clear()

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------- etkileşim
    # Tuval koordinatını tahtadaki hücreye dönüştürür.
    def _cell_at(self, x, y):
        c = int((x - self.ox) // self.cell)
        r = int((y - self.oy) // self.cell)
        if 0 <= r < self.n and 0 <= c < self.n and x >= self.ox and y >= self.oy:
            return r, c
        return None

    # Sol tık döngüsünü veya sağ tık yıldız/boş geçişini uygular.
    def _click(self, event, step: int) -> None:
        cell = self._cell_at(event.x, event.y)
        if cell is None or not self.session:
            return
        self.cursor = cell
        if step > 0:
            changed = self.session.cycle(cell)
        else:
            value = None if self.session.value(cell) == YILDIZ else YILDIZ
            changed = self.session.set(cell, value)
        if changed:
            self._after_move()
        else:
            self.redraw()

    # Ok tuşuyla etkin hücreyi tahtada hareket ettirir.
    def _move_cursor(self, dr, dc) -> None:
        r, c = self.cursor
        self.cursor = (min(max(r + dr, 0), self.n - 1), min(max(c + dc, 0), self.n - 1))
        self.redraw()

    # Klavye komutuyla imleçteki hücreye sembol yazar.
    def _set_at_cursor(self, value) -> None:
        if self.session and self.session.set(self.cursor, value):
            self._after_move()

    # Klavye boşluk kısayoluyla imleçteki sembolü döndürür.
    def _cycle_at_cursor(self) -> None:
        if self.session and self.session.cycle(self.cursor):
            self._after_move()

    # Son hamleyi geri alıp arayüzü yeniler.
    def undo(self) -> None:
        if self.session and self.session.undo():
            self._after_move()

    # Geri alınmış hamleyi yineleyip arayüzü yeniler.
    def redo(self) -> None:
        if self.session and self.session.redo():
            self._after_move()

    # Tahtadaki oyuncu girişlerini temizler.
    def clear(self) -> None:
        if self.session and self.session.clear():
            self._after_move()

    # Çözücünün bulduğu zorunlu hamleyi tahtada vurgular.
    def show_hint(self) -> None:
        """Bir sonraki zorunlu hamleyi ve dayandığı kuralı gösterir (hamleyi yapmaz).

        Tahtada çözümle uyuşmayan bir hücre varsa önce onu gösterir; çünkü yanlış
        bir sembolün üzerine kurulan her çıkarım da yanlış olur.
        """
        s = self.session
        if not s or s.finished:
            return
        self.hint = s.hint()
        if self.hint is not None:
            self.cursor = self.hint.cell
        self.redraw()

    # Hamle sonrası hata uyarılarını, çizimi ve bitiş durumunu günceller.
    def _after_move(self) -> None:
        self.hint = None                    # ipucu bir sonraki hamleye kadar geçerli
        current = self._current_violations()
        self._revealed &= current           # düzeltilen ihlal hemen kaybolur
        self._cancel_reveal()
        if current - self._revealed:        # yeni ihlal: gecikmeyle göster
            self._reveal_job = self.after(self.error_delay_ms, self._reveal_errors)
        self.redraw()
        if self.session.finished:
            self._start_pulse()

    # ------------------------------------------------------------- bitiş dalgası
    # Çözüm tamamlanınca sembolleri kısa bir dalgayla vurgular.
    def _start_pulse(self) -> None:
        """Semboller sol üstten sağ alta dalga hâlinde çok hafif büyüyüp küçülür."""
        self._cancel_pulse()
        start = time.monotonic()

        # Animasyonun her karesini çizip süre bitince sonucu açar.
        def frame():
            self._pulse_t = time.monotonic() - start
            if self._pulse_t * 1000 >= self.pulse_ms:
                self._pulse_t = None
                self._pulse_job = None
                self.redraw()
                self._show_result()
                return
            self.redraw()
            self._pulse_job = self.after(30, frame)

        frame()

    # Devam eden bitiş animasyonunu güvenle durdurur.
    def _cancel_pulse(self) -> None:
        if self._pulse_job is not None:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        self._pulse_t = None

    # Hücrenin bitiş dalgasındaki büyütme katsayısını hesaplar.
    def pulse_scale(self, r: int, c: int) -> float:
        """Dalga sırasında (r, c) hücresindeki sembolün ölçeği (1.0 = normal)."""
        if self._pulse_t is None:
            return 1.0
        total = self.pulse_ms / 1000
        delay, length = total * 0.05, total * 0.45   # en geç hücre: 10 * 0,05 + 0,45 = 0,95
        u = (self._pulse_t - (r + c) * delay) / length
        if not 0 <= u <= 1:
            return 1.0
        return 1 + PULSE_AMPLITUDE * math.sin(math.pi * u)

    # Tahtadaki mevcut kural ihlallerini tek yerde toplar.
    def _current_violations(self) -> set:
        s = self.session
        return set(violations(s.board, s.puzzle.links, n=self.n)) if s else set()

    # Bekleyen gecikmeli hata uyarısını iptal eder.
    def _cancel_reveal(self) -> None:
        if self._reveal_job is not None:
            self.after_cancel(self._reveal_job)
            self._reveal_job = None

    # Süresi dolan kural ihlallerini tahtada görünür yapar.
    def _reveal_errors(self) -> None:
        self._reveal_job = None
        self._revealed = self._current_violations()
        self.redraw()

    # ------------------------------------------------------------- bitiş
    # Açık sonuç penceresini kaldırır.
    def _close_result(self) -> None:
        if self._result_win is not None:
            self._result_win.destroy()
            self._result_win = None

    # Tamamlanan oyunun özetini tahtanın ortasında gösterir.
    def _show_result(self) -> None:
        """Sonuç, ayrı pencere yerine tahtanın tam ortasında gösterilir (tam ekranda
        da arkada kalmaz)."""
        self._close_result()
        t, s = self.theme, self.session
        win = tk.Frame(self, bg=t.panel, padx=36, pady=24, highlightthickness=2,
                       highlightbackground=t.accent)
        win.place(in_=self.canvas, relx=0.5, rely=0.5, anchor="center")
        self._result_win = win
        tk.Label(win, text=t.done_message, font=(FONT, 16, "bold"), bg=t.panel, fg=t.text).pack()
        tk.Frame(win, bg=t.accent, height=2, width=60).pack(pady=10)
        grid = tk.Frame(win, bg=t.panel)
        grid.pack()
        rows = [("Süre", fmt_time(s.elapsed())), ("Hamle", s.moves), ("Geri alma", s.undos),
                ("İpucu", s.hints)]
        if self.daily_mode:
            stats = StatsStore(n=self.n)
            stats.record_daily(self.day, int(s.elapsed()), s.moves, s.undos, s.hints)
            rows.extend((("Seri", stats.streak(self.day)), ("En iyi seri", stats.best_streak())))
        for i, (k, v) in enumerate(rows):
            tk.Label(grid, text=k, font=(FONT, 11), bg=t.panel, fg=t.text_muted).grid(
                row=i, column=0, sticky="w", padx=(0, 28))
            tk.Label(grid, text=str(v), font=(FONT, 11, "bold"), bg=t.panel, fg=t.text).grid(
                row=i, column=1, sticky="e")
        tk.Button(win, text="Yeni bulmaca", command=self.new_puzzle, font=(FONT, 11), bg=t.cell_fixed,
                  fg=t.text, relief="flat", padx=16, pady=6, activebackground=t.cell_fixed,
                  activeforeground=t.text, cursor="hand2").pack(pady=(16, 0))

    # ------------------------------------------------------------- saat
    # Sayacı ve zamanlanmış sessiz dakika mesajını yeniler.
    def _tick(self) -> None:
        if self.session:
            self.lbl_timer.config(text=fmt_time(self.session.elapsed()))
        sm = self.theme.silent_minute
        now = datetime.now()
        on = bool(sm) and now.date() == self.day and (now.hour, now.minute) == sm
        if on and not self.lbl_silent.winfo_ismapped():
            self.lbl_silent.pack(padx=20, before=self.canvas)
        elif not on and self.lbl_silent.winfo_ismapped():
            self.lbl_silent.pack_forget()
        self.after(500, self._tick)

    # ------------------------------------------------------------- çizim
    # Tahta boyutunu kullanılabilir tuval alanına göre hesaplar.
    def _layout(self) -> None:
        w = max(self.canvas.winfo_width(), 1)
        h = max(self.canvas.winfo_height(), 1)
        board = max(min(w, h) - 2 * 12 * self.scale, self.n)
        self.cell = board / self.n
        self.ox = (w - board) / 2
        self.oy = (h - board) / 2

    # Satır ve sütun adresini tuvaldeki sol üst koordinata çevirir.
    def _xy(self, r, c):
        return self.ox + c * self.cell, self.oy + r * self.cell

    # Tahtayı, sembolleri, seçimleri ve hata işaretlerini yeniden çizer.
    def redraw(self) -> None:
        t, cv, s = self.theme, self.canvas, self.session
        self._layout()
        cv.delete("all")
        size = self.cell * self.n
        if s is None:
            cv.create_text(self.ox + size / 2, self.oy + size / 2,
                           text="Bulmaca hazırlanıyor…", fill=t.text_muted, font=(FONT, 13))
            self.lbl_error.config(text="")
            for b in (self.btn_undo, self.btn_hint, self.btn_clear):
                b.config(state="disabled")
            return
        # Yalnızca gecikmesi dolmuş (açığa çıkmış) ve hâlâ geçerli ihlaller gösterilir.
        shown = sorted(self._revealed & self._current_violations())
        errors = {cell for kind, cells in shown for cell in cells}
        broken = {tuple(cells) for kind, cells in shown if kind == "sign"}
        for r in range(self.n):
            for c in range(self.n):
                x, y = self._xy(r, c)
                fill = t.cell_fixed if s.is_fixed((r, c)) else t.cell
                cv.create_rectangle(x, y, x + self.cell, y + self.cell, fill=fill,
                                    outline=t.grid_line, width=max(1, int(self.cell / 40)))
                if (r, c) in errors:
                    self._draw_stripes(x, y)
                v = s.value((r, c))
                if v is not None:
                    self._draw_symbol(x + self.cell / 2, y + self.cell / 2, v,
                                      self.pulse_scale(r, c))
        if not s.finished:
            x, y = self._xy(*self.cursor)
            cv.create_rectangle(x + 1, y + 1, x + self.cell - 1, y + self.cell - 1,
                                outline=t.text_muted, width=1, dash=(2, 2))
        if self.hint is not None:
            # İpucu yalnızca kutuyu belirtir (metin yok): doldurulacak doğru kutu
            # ipucu renginde, yanlış dolu kutu hata renginde kalın çerçeveyle.
            wrong = self.hint.value is None
            x, y = self._xy(*self.hint.cell)
            cv.create_rectangle(x + 2, y + 2, x + self.cell - 2, y + self.cell - 2,
                                outline=t.error_color if wrong else t.hint_color,
                                width=max(4, int(self.cell / 18)))
        cv.create_rectangle(self.ox, self.oy, self.ox + size, self.oy + size,
                            outline=t.grid_line, width=max(1, int(self.cell / 40)))
        for (a, b), kind in s.puzzle.links.items():
            self._draw_sign(a, b, kind, (a, b) in broken or (b, a) in broken)
        self.lbl_error.config(
            text="\n".join(violation_messages(s.board, s.puzzle.links, shown, self.n)[:2]),
            fg=t.error_color)
        self.btn_undo.config(state="normal" if s.can_undo() else "disabled")
        self.btn_hint.config(state="disabled" if s.finished else "normal")
        self.btn_clear.config(state="disabled" if s.finished else "normal")
        self.btn_size.config(state="normal")

    # Hatalı hücreleri renge ek olarak çizgili desenle ayırt eder.
    def _draw_stripes(self, x, y) -> None:
        """Hatalı hücreyi çapraz çizgilerle tarar (renge ek olarak desenle de belli olsun)."""
        cell, step = self.cell, max(self.cell / 7, 6)
        w = max(2, int(cell / 30))
        s = step
        while s < 2 * cell:
            a = min(s, cell)
            self.canvas.create_line(x + a, y + s - a, x + s - a, y + a,
                                    fill=self.theme.error_color, width=w)
            s += step

    # Hilal veya yıldızı hücre merkezine tema renkleriyle çizer.
    def _draw_symbol(self, cx, cy, value, scale: float = 1.0) -> None:
        t = self.theme
        R = self.cell * 0.38 * scale
        if value == HILAL:
            self.canvas.create_polygon(crescent_points(cx, cy, R), fill=HILAL_COLOR,
                                       outline=HILAL_COLOR, width=max(1, int(self.cell / 40)),
                                       stipple="")
        else:
            self.canvas.create_polygon(star_points(cx, cy, R * 1.1), fill=YILDIZ_COLOR,
                                       outline="#FF8790", width=max(1, int(self.cell / 55)))

    # Komşu hücreler arasındaki eşitlik/farklılık işaretini çizer.
    def _draw_sign(self, a, b, kind, broken: bool = False) -> None:
        t, cv = self.theme, self.canvas
        xa, ya = self._xy(*a)
        xb, yb = self._xy(*b)
        cx = (xa + xb) / 2 + self.cell / 2
        cy = (ya + yb) / 2 + self.cell / 2
        rad = self.cell * 0.14
        color = t.error_color if broken else t.sign_color
        cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=t.sign_bg,
                       outline=color, width=max(1, int(self.cell / 40)) * (2 if broken else 1))
        k = rad * 0.5
        w = max(1, int(self.cell / 32))
        if kind == SAME:
            for dy in (-k * 0.55, k * 0.55):
                cv.create_line(cx - k, cy + dy, cx + k, cy + dy, fill=color, width=w)
        else:
            cv.create_line(cx - k, cy - k, cx + k, cy + k, fill=color, width=w)
            cv.create_line(cx - k, cy + k, cx + k, cy - k, fill=color, width=w)


# Uygulamayı başlatır ve Windows'ta keskin DPI çizimi ister.
def run(day: date | None = None) -> None:
    try:  # Windows'ta keskin çizim
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(day, start_screen=True).mainloop()
