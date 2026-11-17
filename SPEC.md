# Hilal & Yıldız — Tango Tarzı Günlük Mantık Oyunu (Python)

Bu belge, LinkedIn Tango'sunu inceleyerek çıkardığımız bulguların özeti ve Claude Code ile geliştirilecek projenin şartnamesidir. Claude Code'a ilk iş olarak bu dosyayı okutun.

## 1. Amaç
6×6 ızgarada iki sembolle (hilal ☾ ve yıldız ★) oynanan, her gün herkese aynı bulmacayı veren, tek çözümlü ve tahmin gerektirmeyen bir mantık oyunu. Python ile yazılacak. Tema her gün tarihe göre değişir. İlk tema **10 Kasım**'dır.

> Not: "Kızılay" bir kurumun adıdır. Oyunda kurum logosu kullanılmaz. Semboller sadece **hilal** ve **yıldız** şekilleridir, kodda çizilir (font glifine bağımlı olmayın).

## 2. Oyun kuralları

### Yazılı kurallar (LinkedIn Tango ile aynı)
1. Her satır ve her sütunda tam **3 hilal ve 3 yıldız** olur.
2. Yan yana veya alt alta **3 aynı sembol** olamaz (çapraz sayılmaz).
3. İki hücre arasındaki **`=`** işareti: iki hücre aynı olmalı.
4. İki hücre arasındaki **`×`** işareti: iki hücre farklı olmalı.

### Yazılı olmayan kurallar (mentör notu ve bulgularımız)
- **Her bulmacanın tam olarak 1 çözümü vardır.** (Tek çözüm yoksa oyun adil olmaz.)
- **Tahmin gerekmez.** Her adımda mantıkla zorunlu bir hamle bulunabilir.
- Herkes aynı gün aynı bulmacayı alır (günlük tohum).
- Bulmacalar **minimal** olmalı: her ipucu gerekli olmalı, fazlalık ipucu olmamalı.
- Zorluk haftanın günüyle artar (Pzt kolay → Paz zor).
- **Belirsiz nokta:** Klasik Binairo'daki "iki satır/sütun aynı olamaz" kuralı Tango'da var mı? Kaynaklar çelişiyor. Kodda `UNIQUE_LINES = False` ayarı olarak tutulsun. Mentörle teyit edilecek.

## 3. Sayısal bulgular (Python ile hesapladık)
| Ölçüt | Değer |
|---|---|
| Satır başına geçerli dizilim | 14 |
| Tüm geçerli 6×6 çözüm ızgarası | 11.222 |
| Satırları ve sütunları birbirinden farklı olanlar | 4.140 |
| Üretilen bulmacalarda ortalama ipucu | ~11,4 (min 9, maks 15) |
| Ortalama sabit sembol / işaret | ~5,5 / ~6,0 |

Sonuç: Çözüm uzayı küçük. Tüm ızgaralar bellekte tutulabilir, çözücü ve üreteç hızlı olur.

## 4. Üretim mantığı (ipuçları neye göre veriliyor?)
LinkedIn kendi yöntemini yayınlamıyor. Bizim yöntemimiz:
1. Gün numarasından **tohum** (seed) üret. Aynı gün herkes aynı bulmacayı alır.
2. Tohumla bir geçerli çözüm ızgarası seç.
3. Başlangıçta **tüm** hücreler sabit ve tüm komşu çiftlere işaret verilmiş kabul et.
4. Ipuçlarını tohumlu rastgele sırayla çıkar. Çıkarınca hâlâ (a) tek çözüm kalıyorsa ve (b) mantık çözücüsü tahminsiz çözebiliyorsa çıkarma kalıcı olur. Aksi halde ipucu geri konur.
5. Sonuç minimal bir ipucu kümesidir. Aynı çözümden bile farklı çıkarma sırasıyla farklı bulmacalar çıkar (denedik: 6 farklı küme, hepsi tek çözümlü).
6. Kalite filtreleri (eklenecek):
   - İpuçları tahtaya dengeli dağılmalı, tek köşeye yığılmamalı.
   - İlk hamle görünür olmalı (başlangıçta en az bir hücre doğrudan çıkarılabilmeli).
   - Sabit sembol ve işaret karışımı dengeli olmalı (örneğin hiç işaretsiz bulmaca olmasın).
   - Aynı bulmaca tekrar çıkmasın.

## 5. Zorluk puanlama
Mantık çözücüsü teknikleri sırayla uygular. Bulmaca için gereken **en gelişmiş teknik** zorluğu belirler:
1. Çift (`●●_` → boşluk ters)
2. Boşluk (`●_●` → orta ters)
3. Sayma (satır/sütunda 3'e ulaşan sembolün kalanı ters)
4. `=` / `×` zincirleri
5. Varsayım ve çelişki (zor bulmacalar)

Hafta günü → zorluk eşlemesi (ayarlanabilir): Pzt-Salı kolay, Çar-Per orta, Cum-Cmt zor, Paz en zor. Üreteç, hedef zorluğu tutturana kadar farklı tohum alt-dizileri dener.

## 6. Mimari (öneri)
```
hilal_yildiz/
  game/
    rules.py       # satır/sütun doğrulama, üçlü kontrolü, UNIQUE_LINES ayarı
    solver.py      # tam çözüm sayacı (kaba kuvvet) + mantık çözücüsü (tahminsiz)
    generator.py   # tohumlu üretim, minimal ipucu, kalite filtreleri
    difficulty.py  # teknik sırasına göre zorluk puanı
    daily.py       # tarih -> tohum -> bulmaca, hafta günü zorluğu
  themes/
    base.py        # Tema veri yapısı (renkler, başlık, mesajlar, saat)
    calendar.py    # tarih -> tema eşlemesi (10 Kasım dahil)
  ui/
    app.py         # tkinter arayüzü (Canvas ile hilal ve yıldız çizimi)
  stats/
    store.py       # JSON: süre, hamle, geri alma, ipucu, seri (streak)
  tests/
  main.py
```
Arayüz için `tkinter` önerilir (Python ile gelir, kurulum gerektirmez). pygame de olur.

## 7. Oyun içi özellikler
- Sol tık döngüsü: boş → hilal → yıldız → boş. Sağ tık yıldız ile boş arasında geçiş yapar.
- Sabit hücreler kilitli.
- Anlık hata gösterimi (üçlü ihlali, sayı aşımı) isteğe bağlı.
- **İpucu butonu:** Çözücünün bir sonraki **zorunlu** hamlesini ve hangi kuralla bulunduğunu gösterir ("sayma kuralı: bu satırda 3 hilal var").
- Geri al / yeniden yap, süre sayacı.
- Bitince sonuç ekranı: süre, ipucu sayısı, **seri (streak)**, paylaşılabilir metin sonucu.
- Günde bir resmi bulmaca. Pratik modu (rastgele tohum) ayrı olabilir.

## 8. Tema: 10 Kasım
10 Kasım, Atatürk'ü Anma Günü'dür. **Tema sakin ve saygılı olmalı**: konfeti, parti efekti ve neşeli animasyon kullanılmaz.
- Renk paleti: Türk bayrağından türeyen **kırmızı (#E30A17)** ve **beyaz**, koyu gri arka plan. Hilal beyaz, yıldız kırmızı. Ayırt edilebilirlik ve renk körlüğü için semboller **şekil olarak da** farklı olmalı (sadece renge güvenmeyin).
- Başlık/alt başlık örneği: "10 Kasım" ve kısa, ölçülü bir anma ifadesi. Metni sen ve ekibin belirleyin.
- Opsiyonel: Saat **09.05**'te bir dakikalık sessiz mod (ses yok, hafif bir bilgi satırı). Zorunlu değil, ekip kararı.
- Tema mimarisi **tarih tabanlı olsun**: `calendar.py` içinde `{(ay, gün): Tema}` sözlüğü ve bir varsayılan tema. Böylece diğer özel günler sonradan eklenir.
- Bu tema için bulmaca zorluğunu özel bir değere sabitlemeyin. Hafta günü kuralı geçerli kalsın.

## 9. Test planı
- Her geçerli ızgara kuralları sağlıyor mu (11.222 sayısı birim testle doğrulanır).
- Üretilen her bulmaca için: çözüm sayısı == 1 ve mantık çözücüsü tamamen çözüyor.
- Minimallik: bir ipucu çıkarılınca bulmaca bozulmalı.
- Aynı tarih → aynı bulmaca (determinizm).
- 365 günlük tohumlarda üretim süresi ve tekrar kontrolü.

## 10. Geliştirme sırası (kilometre taşları)
1. `rules.py`, `solver.py` (mevcut `reference/gen.py` kodundan taşı) ve testler.
2. `generator.py` + kalite filtreleri + `difficulty.py`.
3. `daily.py` ve tema sistemi (10 Kasım dahil).
4. `ui/app.py` (hilal ve yıldız çizimi, tıklama, ipucu butonu).
5. İstatistik, seri, sonuç ekranı.
6. Cila: erişilebilirlik, ayarlar, kısa kullanım kılavuzu.

## 11. Açık sorular (ekibin ve mentörün cevabı gerekli)
1. Satır/sütun tekrarı yasağı var mı (`UNIQUE_LINES`)?
2. Mentörün "yazılı olmayan kural" derken kastettiği şey tam olarak bu listeyle örtüşüyor mu?
3. Oyun "LinkedIn Tango'sunun kopyası" mı olacak, yoksa kendi ayırt edici özelliği (örneğin farklı ızgara boyutu, ek kısıt türü) olacak mı? Mentör sınırı netleştirsin.
4. Arayüz: tkinter mi pygame mi?
5. 09.05 sessiz modu istiyor muyuz?

## 12. Kaynaklar
- Tango Unlimited kurallar: https://www.tango-unlimited.com/rules
- Strateji: https://8tango.com/tips/strategy
- Çözücü yazısı: https://www.lunavi.com/blog/creating-a-solver-for-linkedins-tango-puzzle-game
- Takuzu: https://en.wikipedia.org/wiki/Takuzu
- QUBO formülasyonu: https://export.arxiv.org/abs/2501.00002
- LinkedIn Yardım: https://www.linkedin.com/help/linkedin/answer/a6863543

---

## Claude Code için başlangıç komutu (yapıştır)
```
SPEC.md dosyasını oku. Önce 6. maddedeki mimariyi kur, reference/gen.py içindeki
kuralları ve çözücüyü game/rules.py ve game/solver.py'a taşı, 9. maddedeki
testleri yaz ve çalıştır. Sonra generator.py'yi tohumlu, minimal ve kalite
filtreli olarak yaz. UI'a geçmeden önce bana test sonuçlarını göster.
```
