# Hedef Takip (Target Tracker)

Web kamerası açıkken fareyle bir alan seçip o alandaki nesneyi hedef olarak belirleyen ve canlı takip eden basit bir OpenCV uygulaması. Hedef kadrajdan çıkarsa program hedefi kayıp olarak işaretler, geri girdiğinde aynı nesneyi tekrar bulup takibe devam eder.

## Özellikler

- **Fareyle hedef seçimi:** Kamera görüntüsü üzerinde sürükleyerek alan çizin, takip hemen başlar.
- **Güçlü takip:** Kurulu OpenCV sürümüne göre CSRT, KCF veya MIL takipçisini otomatik seçer (CSRT en doğru olanıdır).
- **Hedef doğrulama:** Takip kutusunun içeriği hedefin renk histogramıyla her karede karşılaştırılır. Takipçi başka bir nesneye kayarsa hedef kayıp sayılır.
- **Otomatik yeniden yakalama:** Hedef kayıp olunca tüm kare çok ölçekli şablon eşleştirmesiyle taranır. Aynı nesne bulunursa takip kaldığı yerden devam eder, benzemeyen nesnelere kilitlenmez.
- **Yavaş güncellenen referans:** İlk seçim sabit kalır, ayrıca güvenli takip sırasında "son görünüm" güncellenir. Böylece nesnenin boyutu veya ışık koşulları değişse de eşleşme bozulmaz.
- **Hareket izi:** Hedefin son konumları çizgiyle gösterilir.
- **Sade arayüz:** FPS göstergesi, tek satırlık durum mesajı ve kapat butonu.

## Gereksinimler

- Python 3.8 veya üzeri
- Bir web kamerası
- `opencv-contrib-python` ve `numpy`

## Kurulum

```bash
git clone <repo-adresi>
cd <repo-klasoru>

pip install opencv-contrib-python numpy
```

> Sadece `opencv-python` kuruluysa program MIL takipçisiyle çalışır ama CSRT kadar hassas değildir. En iyi sonuç için `opencv-contrib-python` kurun. İkisini aynı ortamda birlikte kurmayın.

## Kullanım

```bash
python target_tracker.py
```

1. Kamera penceresi açılır.
2. Fareyle takip etmek istediğiniz nesnenin etrafına sıkı bir dikdörtgen sürükleyin.
3. Takip başlar, kutu `LOCKED` etiketiyle nesneyi izler.
4. Nesne kadrajdan çıkarsa sol altta "Hedef kayip, araniyor..." yazar. Nesne geri girince otomatik olarak yeniden yakalanır.

### Kontroller

| Girdi | İşlev |
|---|---|
| Fareyle sürükle | Yeni hedef seç (takip sırasında da çalışır) |
| `R` | Hedefi sıfırla |
| `Q` veya `ESC` | Çıkış |
| `CLOSE` butonu | Çıkış |

### Ekran göstergeleri

| Gösterge | Anlamı |
|---|---|
| Sarı kutu, `LOCKED` | Hedef güvenle takip ediliyor |
| Turuncu kutu, `ZAYIF` | Kutunun içeriği hedefe az benziyor, takip kaybolabilir |
| Kırmızı kesikli kutu | Hedefin son bilinen konumu (arama modunda) |
| Sol alt yazı | Durum mesajı, arama sırasında `(anlık eşleşme / eşik)` değeri |
| Sağ üst | FPS |

## Nasıl Çalışır

```
Fareyle secim ──► TargetModel (renk histogrami + sablon) + Takipci (CSRT/KCF/MIL)
                        │
                        ▼
     Her karede: takipci kutuyu gunceller
                        │
          Kutu hedefe benziyor mu? (histogram korelasyonu)
             ├── Evet ──► TRACKING (guvenli takip)
             └── Hayir, ust uste N kare ──► SEARCHING
                                               │
                        Tum kare, 9 olcekte sablon eslesmesi
                                               │
                     Esik + renk dogrulamasi gecerse ──► takipci yeniden baslatilir
```

Takip tamamen görüntü üzerinden yapılır, nesne türü fark etmez. Sınıflandırma veya derin öğrenme modeli kullanılmaz.

## Ayarlar

`target_tracker.py` dosyasının başındaki sabitlerle davranış ayarlanabilir:

| Sabit | Varsayılan | Açıklama |
|---|---|---|
| `APPEARANCE_MIN` | `0.45` | Takip kutusunun hedefe minimum renk benzerliği |
| `LOST_FRAMES` | `6` | Bu kadar kare üst üste düşük skor gelirse hedef kayıp sayılır |
| `REACQUIRE_NCC` | `0.60` | Yeniden yakalamada şablon eşleşme eşiği |
| `REACQUIRE_HIST` | `0.55` | Yeniden yakalamada renk benzerliği eşiği |
| `SEARCH_EVERY` | `2` | Kayıpken kaç karede bir tarama yapılacağı |
| `SEARCH_DOWNSCALE` | `0.5` | Tarama hızı için karenin küçültme oranı |
| `SEARCH_SCALES` | `0.6 … 1.75` | Aramada denenen boyut oranları |
| `REFRESH_EVERY` | `20` | "Son görünüm" şablonunun yenileme aralığı (kare) |
| `REFRESH_MIN_SCORE` | `0.80` | Yenileme için gereken minimum benzerlik |
| `TRAIL_LENGTH` | `40` | İz çizgisindeki nokta sayısı |

**İpuçları**

- Hedef geri gelince bulunamıyorsa `REACQUIRE_NCC` ve `REACQUIRE_HIST` değerlerini düşürün (örn. `0.5` ve `0.45`).
- Yanlış nesneyi yakalıyorsa bu değerleri yükseltin.
- Hedefi çok çabuk kaybediyorsa `APPEARANCE_MIN` değerini düşürün veya `LOST_FRAMES` değerini artırın.
- Seçimi nesneyi sıkı saracak şekilde yapın. Arka plan çok girerse takipçi arka plana kayabilir.

## Sınırlamalar

- Şablon eşleştirme, nesnenin ciddi biçimde döndürülmesine veya bambaşka bir açıdan görünmesine dayanıklı değildir.
- Aynı renkte ve görünümde birden fazla nesne varsa yanlış eşleşme olabilir.
- Tamamen tek renkli, dokusuz nesnelerde yeniden yakalama zayıf kalabilir.
- Kamera 0 numaralı cihaz olarak açılır. Windows'ta önce `CAP_DSHOW` denenir, olmazsa varsayılan arka uç kullanılır.

## Sorun Giderme

| Sorun | Çözüm |
|---|---|
| `Web kamera acilamadi.` | Kameranın başka bir uygulama tarafından kullanılmadığından emin olun, gerekirse kamera indeksini (`cv2.VideoCapture(0)`) değiştirin |
| `Takipci bulunamadi` | `pip install opencv-contrib-python` ile kurun |
| Takip sık sık kayboluyor | Ortam ışığını sabitleyin, seçimi nesneye daha sıkı yapın, ayarlar bölümündeki eşikleri deneyin |

## Proje Yapısı

```
.
├── target_tracker.py   # Uygulamanın tamamı
└── README.md
```