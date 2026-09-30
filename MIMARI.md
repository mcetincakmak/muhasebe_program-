# Mimari (geliştirici notları)

## Katmanlar

```
app/
  main.py          Uygulama girişi: güvenlik katmanı, yönlendiricilerin bağlanması, açılışta göçler
  gorevler.py      Arka plan: her firmanın günlük e-fatura taraması
  core/            Çekirdek — iş kuralı içermez
    yapilandirma   Sürüm, veri klasörü (FATURA_VERI)
    db             Firma başına ayrı SQLite + sistem veritabanı; aktif firma bağlam değişkeninde
    gocler         Numaralı veritabanı sürümleri, göç öncesi otomatik yedek, 1.x'ten geçiş
    guvenlik       Şifre, oturum, her istekte kimlik + firma + izin + lisans denetimi
    yetki          Roller ve yol → izin kuralları (varsayılan: yazma yalnızca yöneticiye)
    lisans         Ed25519 imzalı, internetsiz lisans; deneme süresi; süre bitince salt okuma
    ortak          Hata, firma bilgisi, kilitler
  entegrator/      Özel entegratör eklentileri (temel arayüz + deneme + qnb)
  servisler/       İş kuralları: ubl (UBL-TR), okuma (OCR/AI), eslestirme, stok, tarama
  api/             HTTP uç noktaları; her dosya bir APIRouter
  static/          Arayüz (derleme gerektirmeyen tek sayfa uygulama)
tests/             Uçtan uca testler (python -m pytest tests)
tools/             Lisans üretme aracı (müşteriye verilmez)
```

Bağımlılık yönü: `api → servisler → core`, `servisler → entegrator → core`. `core` hiçbir üst katmanı içe aktarmaz.

## Çok firma

- Sistem veritabanı (`veri/sistem.db`): firmalar, kullanıcılar, firma yetkileri, oturumlar, lisans.
- Her firma: `veri/firmalar/<id>/fatura.db`, `belgeler/`, `yedekler/`.
- İstek başında `core.guvenlik.oturum` aktif firmayı belirler; `db.islem()` otomatik olarak o dosyayı açar.
  İş kodu firma kimliği taşımaz, bu yüzden bir firmanın verisinin diğerine karışması yapısal olarak engellenir.
- İstek dışı kod (zamanlayıcı, betikler) `with db.firma_baglami(fid):` kullanır.

## Veritabanı değişikliği nasıl yapılır

1. `core/gocler.py` içinde yeni bir fonksiyon yazın (ör. `_f3_vade_alani`).
2. `FIRMA_GOCLERI` (veya `SISTEM_GOCLERI`) listesinin **sonuna** yeni numarayla ekleyin.
3. Mevcut göçleri asla değiştirmeyin. Program açılışta eksik göçleri, öncesinde yedek alarak uygular.
4. Göç tek işlemde çalışır; hata olursa geri alınır. `executescript` kullanmayın (örtük COMMIT yapar), `_betik()` kullanın.

## Yeni uç nokta eklerken

- İlgili `api/*.py` dosyasına `@router.get/post/...` ekleyin; yönlendirici zaten oturum denetimli bağlanır.
- `core/yetki.py` içinde yola uygun kural yoksa: GET "okuma", diğerleri "yonetim" izni ister (güvenli varsayılan).
  Başka rollerin de kullanması gerekiyorsa kural ekleyin ve `tests/` içine yetki testi yazın.

## Yeni entegratör eklemek

1. `entegrator/<ad>.py`: `Entegrator` sınıfından türetin; `kod`, `ad`, `alanlar` ve beş yöntemi uygulayın.
2. `entegrator/__init__.py` içindeki `KAYIT` sözlüğüne ekleyin. Ayarlar ekranı alanları kendiliğinden gösterir.

## Lisans

- Açık anahtar `core/lisans.py` içinde; özel anahtar yalnızca satıcıda (pakette yoktur).
- Anahtar üretme: `python tools/lisans_uret.py --anahtar ozel.pem --musteri "..." --bitis 2027-12-31 --firma 2 --kullanici 5 --makine <kod>`
- Özel anahtar kaybolursa yeni anahtar çifti üretilip yeni sürüm dağıtılmalıdır; eski lisanslar geçersiz olur.

## Test ve kalite

- `python -m pytest tests` — hesaplar, XML, güvenlik, çok firma yalıtımı, roller, lisans, 1.x'ten geçiş.
- `python -m pyflakes app` ve `python -m bandit -r app -ll` temiz tutulmalı.
