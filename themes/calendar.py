"""Tarih -> tema eşlemesi. Yeni özel günler THEMES sözlüğüne eklenir."""
from __future__ import annotations

from datetime import date

from .base import Theme

DEFAULT = Theme(
    key="default",
    title="10 Kasım",
    subtitle="Her satır ve sütunda 3 hilal, 3 yıldız.",
    bg="#000000",
    panel="#101010",
    cell="#080808",
    cell_fixed="#1A1A1A",
    grid_line="#454545",
    text="#F5F5F5",
    text_muted="#B8B8B8",
    accent="#E30A17",
    hilal_color="#FFFFFF",
    yildiz_color="#E30A17",
    sign_color="#E0E0E0",
    sign_bg="#000000",
    error_color="#C62828",
    hint_color="#2E7D32",
    done_message="Bulmaca tamamlandı.",
    share_tag="",
    dates_line="1881 – 1938",
    horizontal_eight=True,
)

# 10 Kasım: sakin ve saygılı. Konfeti/animasyon yok. Bayraktan türeyen kırmızı
# (#E30A17) ve beyaz, koyu gri zemin. Hilal beyaz, yıldız kırmızı; semboller
# şekil olarak da farklı (renk körlüğü için).
TEN_NOVEMBER = Theme(
    key="10-kasim",
    title="10 Kasım",
    subtitle="Mustafa Kemal Atatürk'ü saygı ve özlemle anıyoruz.",
    bg="#000000",
    panel="#101010",
    cell="#080808",
    cell_fixed="#1A1A1A",
    grid_line="#454545",
    text="#F5F5F5",
    text_muted="#B8B8B8",
    accent="#E30A17",
    hilal_color="#FFFFFF",
    yildiz_color="#E30A17",
    sign_color="#E0E0E0",
    sign_bg="#000000",
    error_color="#F2C94C",   # kırmızı sembolle karışmasın diye sarı
    hint_color="#7FB3FF",
    done_message="Bulmaca tamamlandı.",
    share_tag="10 Kasım",
    silent_minute=(9, 5),
    silent_message="09.05 · Saygıyla anıyoruz.",
    top_band="#E30A17",
    emblem=True,
    dates_line="1881 – 1938",
    horizontal_eight=True,
)

THEMES: dict[tuple[int, int], Theme] = {
    (11, 10): TEN_NOVEMBER,
}


# Verilen tarih için özel tema varsa onu, yoksa varsayılanı seçer.
def theme_for(d: date) -> Theme:
    return THEMES.get((d.month, d.day), DEFAULT)
