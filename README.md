# Görüntü İşleme Takip Uygulaması

Bu proje, webcam üzerinden mavi nesneleri tespit edip kullanıcı tarafından seçilen hedefi takip eden basit bir Python uygulamasıdır.

## Özellikler

- Webcam akışını açar
- Kullanıcıdan hedef alanı seçmesini ister
- Seçilen hedefi takip eder
- Kapatma butonu ile uygulamayı kapatır

## Gereksinimler

- Python 3.10+
- Webcam

## Kurulum

1. Proje klasörüne geçin.
2. Sanal ortam oluşturun:

```bash
python -m venv .venv
```

3. Sanal ortamı etkinleştirin:

- Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Bağımlılıkları yükleyin:

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
python main.py
```

## Kullanım

1. Uygulama açıldığında hedef alanını sürükleyerek seçin.
2. Seçilen hedef otomatik olarak takip edilir.
3. Hedef, kırmızı "release line" seviyesine erişince olay anlık görüntüsü `atis_kanit.jpg` olarak kaydedilir.
4. Pencerenin üst köşesindeki "CLOSE" butonuna basarak kapatabilirsiniz.

## Proje Yapısı

- `main.py` — ana uygulama kodu
- `test_main.py` — temel davranış testleri
- `requirements.txt` — Python bağımlılıkları
- `.gitignore` — gereksiz dosyaları dışarıda tutar

## Notlar

- Kamera erişimi için bilgisayarınızda uygun kamera sürücüsü olması gerekir.
- Seçilen hedefin görünürlüğü ve aydınlatma durumu takip kalitesini etkileyebilir.
