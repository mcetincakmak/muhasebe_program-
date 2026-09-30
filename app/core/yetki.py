"""Roller ve izinler.

Her API isteği, yolu ve yöntemine göre bir izin gerektirir (aşağıdaki kurallar, ilk eşleşen geçerli).
Kurala uymayan GET istekleri "okuma", diğerleri "yonetim" ister; yani yeni bir uç nokta eklenip
kural yazılmazsa yazma işlemleri varsayılan olarak yalnızca yöneticiye açıktır.
"""
import re

IZIN_ADLARI = {
    "okuma": "Faturaları, carileri, kasayı ve özetleri görme",
    "fatura": "Satış ve iade faturası kesme",
    "alis": "Alış faturaları ve e-fatura taraması",
    "irsaliye": "İrsaliye yükleme ve düzeltme",
    "cari": "Cari ekleme ve düzenleme",
    "stok": "Ürün ve stok işlemleri",
    "kasa": "Tahsilat, ödeme, kasa ve banka",
    "rapor": "Raporlar ve Excel",
    "ayar": "Firma ve entegratör ayarları",
    "yonetim": "Yedek, günlük ve erişim bilgileri",
}

ROLLER = {
    "yonetici": {"ad": "Yönetici", "izinler": set(IZIN_ADLARI)},
    "muhasebe": {"ad": "Muhasebe", "izinler": {"okuma", "fatura", "alis", "irsaliye", "cari", "stok", "kasa", "rapor"}},
    "personel": {"ad": "Personel (irsaliye ve stok)", "izinler": {"irsaliye"}},
    "musavir": {"ad": "Mali müşavir (salt okuma)", "izinler": {"okuma", "rapor"}},
}

# (yöntemler, yol deseni, gereken izin — "a|b" en az biri; None: yalnızca giriş yapmış olmak yeter)
KURALLAR = [
    ("*", r"^/api/(ben|firma-sec|sifre|cikis)$", None),
    ("*", r"^/api/(kullanicilar|firmalar|lisans)(/.*)?$", "sistem"),
    ("*", r"^/api/irsaliyeler(/.*)?$", "irsaliye"),
    ("GET", r"^/api/(cariler|urunler|stok)$", "irsaliye|okuma"),
    ("GET", r"^/belge/", "irsaliye|okuma"),
    ("POST", r"^/api/cariler/\d+/mukellef-sorgula$", "cari|fatura"),
    ("GET", r"^/api/", "okuma"),
    ("GET", r"^/goruntule/", "okuma"),
    ("*", r"^/api/cariler(/.*)?$", "cari"),
    ("*", r"^/api/urunler/\d+/stok-duzelt$", "stok"),
    ("*", r"^/api/(urunler|stok-hareketleri)(/.*)?$", "stok"),
    ("POST", r"^/api/gelen/\d+/stoka-al$", "stok"),
    ("POST", r"^/api/gelen/\d+/iade-taslak$", "fatura"),
    ("*", r"^/api/faturalar(/.*)?$", "fatura"),
    ("*", r"^/api/gelen(/.*)?$", "alis"),
    ("POST", r"^/api/tarama$", "alis"),
    ("*", r"^/api/(hareketler|hesaplar)(/.*)?$", "kasa"),
    ("*", r"^/api/(ayarlar|entegrator-test)$", "ayar"),
]
# GET ile de korunması gereken, "okuma"dan fazlasını isteyen uç noktalar (yukarıdaki genel GET kuralından önce)
GET_OZEL = [
    (r"^/api/(rapor|disa-aktar)$", "rapor"),
    (r"^/api/(ayarlar|entegratorler)$", "ayar"),
    (r"^/api/(yedek|gunluk|erisim)$", "yonetim"),
    (r"^/api/kur$", "fatura|okuma"),
]


def gereken_izin(yontem, yol):
    if yontem == "GET":
        for desen, izin in GET_OZEL:
            if re.match(desen, yol):
                return izin
    for yontemler, desen, izin in KURALLAR:
        if (yontemler == "*" or yontem in yontemler.split(",")) and re.match(desen, yol):
            return izin
    return "okuma" if yontem in ("GET", "HEAD") else "yonetim"


def izinli(izinler, gereken):
    return gereken is None or any(i in izinler for i in gereken.split("|"))
