"""Tema veri yapısı: renkler, başlık, mesajlar, isteğe bağlı sessiz dakika."""
from __future__ import annotations

from dataclasses import dataclass


# Arayüzün tarih ve renk temasına ait değişmez ayarlarını taşır.
@dataclass(frozen=True)
class Theme:
    key: str
    title: str
    subtitle: str
    # Renkler
    bg: str
    panel: str
    cell: str
    cell_fixed: str
    grid_line: str
    text: str
    text_muted: str
    accent: str
    hilal_color: str
    yildiz_color: str
    sign_color: str
    sign_bg: str
    error_color: str
    hint_color: str
    # Mesajlar
    done_message: str = "Bulmaca tamamlandı."
    share_tag: str = ""
    # (saat, dakika) verilirse o dakika boyunca ses olmadan bilgi satırı gösterilir.
    silent_minute: tuple[int, int] | None = None
    silent_message: str = ""
    # Anma günleri için ölçülü süsler (hepsi isteğe bağlı, varsayılan kapalı):
    top_band: str | None = None   # pencerenin en üstünde ince renk şeridi
    emblem: bool = False          # başlığın yanında çizimle bayrak amblemi
    dates_line: str = ""          # alt başlığın altında kısa satır (ör. yıllar)
    horizontal_eight: bool = False  # tarih satırının sonundaki 8'i yatay çiz
    # Kutlama efektleri (konfeti vb.; hiçbir temada yok, alan ileride neşeli günler
    # için ayrılmıştır). Bitişteki hafif büyüyüp küçülme kutlama değil, "tamamlandı"
    # işaretidir ve her temada aynıdır.
    celebrate: bool = False
