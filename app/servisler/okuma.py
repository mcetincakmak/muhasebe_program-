"""İrsaliye ve kağıt fatura fotoğraflarını okur.

İki yöntem vardır (Ayarlar > Belge okuma):
  - ocr : Bilgisayardaki Tesseract ile, ücretsiz ve internetsiz. İrsaliye no, VKN, tarih gibi
          basılı alanları iyi okur; ürün satırlarında zorlanabilir.
  - ai  : Claude API ile (isteğe bağlı, ücretli). El yazısı ve tablolarda daha başarılı.
"""
import base64
import io
import json
import os
import re
import shutil

import requests

from ..core.yapilandirma import KOK

VARSAYILAN_MODEL = "claude-sonnet-5-5"

TALIMAT = """Bu fotoğraf(lar) Türkiye'de düzenlenmiş bir sevk irsaliyesi veya kağıt fatura. Birden fazla fotoğraf varsa aynı belgenin sayfalarıdır.
Belgedeki bilgileri oku ve SADECE aşağıdaki JSON'u döndür (açıklama, markdown veya ``` kullanma):
{
  "belge_turu": "irsaliye" | "fatura" | "diger",
  "belge_no": "irsaliye veya fatura numarası, seri dahil, boşluksuz",
  "tarih": "YYYY-MM-DD (düzenleme tarihi)",
  "gonderen": {"unvan": "", "vkn": "10 haneli VKN veya 11 haneli TCKN, sadece rakam", "vergi_dairesi": "", "adres": "", "ilce": "", "il": "", "telefon": ""},
  "alici": {"unvan": "", "vkn": ""},
  "satirlar": [{"ad": "", "miktar": 0, "birim": "C62|KGM|LTR|MTR|MTK|BX|SET|HUR|DAY|MON", "birim_fiyat": null, "kdv": null}],
  "genel_toplam": null,
  "okunamayan": "okuyamadığın veya emin olmadığın alanlar, kısa"
}
Kurallar: Gönderen, belgeyi düzenleyen (malı gönderen/satan) firmadır. Emin olmadığın alanı boş bırak veya null yaz; tahmin uydurma.
Miktarlar ve fiyatlar sayı olsun (Türk formatındaki 1.250,50 -> 1250.5). Birimi eşleyemezsen "C62" (adet) yaz."""


class OkumaHatasi(Exception):
    pass


def oku(fotolar, api_anahtari, model=None):
    """fotolar: [(mime_type, bytes), ...] -> sözlük"""
    if not api_anahtari:
        raise OkumaHatasi("Otomatik okuma için Ayarlar'a Claude API anahtarı girin. Bilgileri şimdilik elle girebilirsiniz.")
    icerik = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(veri).decode()}}
              for mime, veri in fotolar]
    icerik.append({"type": "text", "text": TALIMAT})
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_anahtari, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model or VARSAYILAN_MODEL, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": icerik}]},
            timeout=120,
        )
    except requests.RequestException as e:
        raise OkumaHatasi(f"Okuma servisine bağlanılamadı: {e}")
    if r.status_code == 401:
        raise OkumaHatasi("Claude API anahtarı geçersiz. Ayarlar'dan kontrol edin.")
    if r.status_code >= 400:
        try:
            mesaj = r.json().get("error", {}).get("message", "")
        except ValueError:
            mesaj = r.text[:200]
        raise OkumaHatasi(f"Okuma servisi hata verdi ({r.status_code}): {mesaj}")
    metin = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    return cozumle(metin)


def cozumle(metin):
    """Modelin döndürdüğü metinden JSON'u çıkarır ve alanları temizler."""
    temiz = re.sub(r"```(?:json)?", "", metin).strip()
    bas, son = temiz.find("{"), temiz.rfind("}")
    if bas < 0 or son < 0:
        raise OkumaHatasi("Belge okunamadı. Fotoğrafı daha net çekip tekrar deneyin veya elle girin.")
    try:
        v = json.loads(temiz[bas:son + 1])
    except json.JSONDecodeError:
        raise OkumaHatasi("Belge okunamadı. Fotoğrafı daha net çekip tekrar deneyin veya elle girin.")

    def sayi(x):
        if x in (None, ""):
            return None
        if isinstance(x, (int, float)):
            return x
        s = str(x).replace(" ", "")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    g = v.get("gonderen") or {}
    g["vkn"] = re.sub(r"\D", "", str(g.get("vkn") or ""))
    if len(g["vkn"]) not in (10, 11):
        g["vkn"] = ""
    tarih = str(v.get("tarih") or "")
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", tarih)
    if m:
        tarih = f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", tarih):
        tarih = ""
    satirlar = []
    for s in v.get("satirlar") or []:
        if not (s.get("ad") or "").strip():
            continue
        satirlar.append({"ad": s["ad"].strip(), "miktar": sayi(s.get("miktar")) or 1,
                         "birim": s.get("birim") or "C62", "birim_fiyat": sayi(s.get("birim_fiyat")),
                         "kdv": sayi(s.get("kdv"))})
    return {
        "belge_turu": v.get("belge_turu") or "diger",
        "belge_no": re.sub(r"\s", "", str(v.get("belge_no") or "")).upper(),
        "tarih": tarih, "gonderen": g, "alici": v.get("alici") or {},
        "satirlar": satirlar, "genel_toplam": sayi(v.get("genel_toplam")),
        "okunamayan": v.get("okunamayan") or "",
    }


# ====================================================================== OCR (Tesseract)
WINDOWS_YOLLARI = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]


# Kurulum betiği Türkçe dil dosyalarını program klasöründeki "tessdata" içine indirir (yönetici izni gerekmez).
# Program klasörü = kurulum.ps1'in bulunduğu kök klasör (app/ değil).
YEREL_TESSDATA = os.path.join(KOK, "tessdata")


def _yerel_tessdata_kullan():
    """Program klasöründeki dil dosyaları varsa Tesseract'a onları kullandırır.
    Yol "--tessdata-dir" ile değil ortam değişkeniyle verilir: pytesseract Windows'ta komut satırı
    ayarlarındaki tırnakları silmez, Tesseract tırnaklı yolu bulamaz ve OCR boş döner."""
    if os.path.isfile(os.path.join(YEREL_TESSDATA, "tur.traineddata")):
        os.environ["TESSDATA_PREFIX"] = YEREL_TESSDATA


def tesseract_bul(ayar_yolu=None):
    for yol in [ayar_yolu] + WINDOWS_YOLLARI:
        if yol and os.path.isfile(yol):
            return yol
    return shutil.which("tesseract")


def ocr_metin(fotolar, tesseract_yolu=None):
    """fotolar: [(mime, bytes)] -> ham metin (sayfalar alt alta)"""
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError:
        raise OkumaHatasi("OCR bileşenleri kurulu değil. baslat.bat dosyasını tekrar çalıştırın.")
    yol = tesseract_bul(tesseract_yolu)
    if not yol:
        raise OkumaHatasi("Tesseract bulunamadı. Kurulum kılavuzundaki Tesseract adımını yapın "
                          "veya Ayarlar'da tesseract.exe yolunu girin.")
    pytesseract.pytesseract.tesseract_cmd = yol
    _yerel_tessdata_kullan()
    diller = "tur+eng"
    try:
        mevcut = pytesseract.get_languages()
        if "tur" not in mevcut:
            diller = "eng"
        elif "eng" not in mevcut:
            diller = "tur"
    except Exception:
        pass
    sayfalar = []
    for _, veri in fotolar:
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(veri))).convert("L")
        except Exception:
            raise OkumaHatasi("Fotoğraf açılamadı. JPEG veya PNG yükleyin.")
        if max(img.size) < 1800:  # küçük fotoğrafları büyüt, OCR daha iyi okur
            oran = 1800 / max(img.size)
            img = img.resize((int(img.width * oran), int(img.height * oran)))
        img = ImageOps.autocontrast(img, cutoff=1)
        try:
            osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT, timeout=30)
            if osd.get("rotate"):
                img = img.rotate(-osd["rotate"], expand=True)
        except Exception:
            pass
        try:
            sayfalar.append(pytesseract.image_to_string(img, lang=diller, config="--psm 3", timeout=90))
        except RuntimeError:  # pytesseract zaman aşımında RuntimeError fırlatır
            raise OkumaHatasi("Fotoğraf okuma çok uzun sürdü. Daha küçük veya net bir fotoğraf deneyin.")
    return "\n".join(sayfalar)


BIRIM_ESLE = {"ADET": "C62", "AD": "C62", "ADT": "C62", "KG": "KGM", "KGM": "KGM", "LT": "LTR", "LİTRE": "LTR",
              "LITRE": "LTR", "MT": "MTR", "METRE": "MTR", "M2": "MTK", "M²": "MTK", "KOLİ": "BX", "KOLI": "BX",
              "KUTU": "BX", "PAKET": "BX", "PK": "BX", "SET": "SET", "TAKIM": "SET", "SAAT": "HUR"}


def _sayi_tr(s):
    s = s.strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _kelime_set(s):
    tr = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUcgiiosu")
    return {k for k in re.findall(r"[a-z0-9]{3,}", (s or "").translate(tr).lower())} - {
        "ltd", "sti", "san", "tic", "limited", "sirketi", "ve", "a.s"}


def ayikla(metin, kendi_vkn="", kendi_unvan=""):
    """OCR metninden belge bilgilerini kurallarla çıkarır."""
    duz = metin.replace("|", " ")
    ust = duz.upper().replace("İ", "I")
    bulgu = {"belge_turu": "diger", "belge_no": "", "tarih": "", "gonderen": {}, "alici": {},
             "satirlar": [], "genel_toplam": None, "okunamayan": ""}

    if re.search(r"IRSAL", ust):
        bulgu["belge_turu"] = "irsaliye"
    elif re.search(r"FATURA", ust):
        bulgu["belge_turu"] = "fatura"

    # --- belge no: önce GİB formatı (3 karakter + yıl + 9 hane), sonra "No:" kalıpları
    gib = re.findall(r"\b([A-Z0-9]{3}20\d{2}\d{9})\b", ust.replace(" ", " "))
    if gib:
        bulgu["belge_no"] = gib[0]
    else:
        m = re.search(r"(?:IRSALIYE|FATURA|BELGE)\s*(?:NO|NUMARASI)\s*[:.]?\s*([A-Z]{0,3}\s?-?\s?\d{3,})", ust) \
            or re.search(r"SER[I1]\s*[:.]?\s*([A-Z]{1,3})\s*(?:SIRA\s*)?NO\s*[:.]?\s*(\d{3,})", ust)
        if m:
            bulgu["belge_no"] = re.sub(r"[\s\-]", "", "".join(g for g in m.groups() if g))

    # --- tarih: "Tarih" kelimesine yakın olanı tercih et
    tarihler = [(m.start(), m.group(1), m.group(2), m.group(3))
                for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", duz)]
    if tarihler:
        tercih = None
        for kelime in ("DÜZENLEME", "DUZENLEME", "SEVK", "TARİH", "TARIH"):
            k = duz.upper().find(kelime)
            if k >= 0:
                tercih = min(tarihler, key=lambda t: abs(t[0] - k))
                break
        _, g, a, y = tercih or tarihler[0]
        if 1 <= int(g) <= 31 and 1 <= int(a) <= 12:
            bulgu["tarih"] = f"{y}-{int(a):02d}-{int(g):02d}"

    # --- VKN/TCKN: etiketli olanlar önce, kendi VKN'miz hariç
    etiketli = re.findall(r"(?:VKN|V\.?K\.?N|VERG[I1]\s*(?:K[I1]ML[I1]K\s*)?NO|VERG[I1]\s*NUMARASI|TCKN|T\.?C\.?\s*K[I1]ML[I1]K\s*NO)"
                          r"\s*[:.]?\s*(\d[\d ]{9,12})", ust)
    adaylar = [re.sub(r"\D", "", v) for v in etiketli] + re.findall(r"(?<!\d)(\d{10,11})(?!\d)", ust)
    adaylar = [v for v in adaylar if len(v) in (10, 11) and v != kendi_vkn and not v.startswith("0")]
    if adaylar:
        bulgu["gonderen"]["vkn"] = adaylar[0]

    # --- vergi dairesi
    m = re.search(r"VERG[İI1]\s*DA[İI1]RES[İI1]\s*[:.]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü ]{3,30})", duz, re.I)
    if m:
        bulgu["gonderen"]["vergi_dairesi"] = re.split(r"\s{2,}|VKN|V\.K|NO", m.group(1).strip(), flags=re.I)[0].strip().title()

    # --- ünvan: belgenin üst kısmındaki, bize ait olmayan ilk firma satırı
    kendi = _kelime_set(kendi_unvan)
    def bizim_mi(satir):
        k = _kelime_set(satir)
        return bool(kendi and k) and len(k & kendi) / min(len(k), len(kendi)) >= 0.5
    satirlar_ust = [x.strip() for x in duz.splitlines()[:30] if len(x.strip()) > 5]
    unvan = ""
    for satir in satirlar_ust:
        if re.search(r"\b(LTD|L[İI]M[İI]TED|A\.?\s?Ş\.?|ANON[İI]M|ŞT[İI]\.?|T[İI]C\.?|SAN\.?)\b", satir, re.I) and not bizim_mi(satir):
            unvan = satir
            break
    if not unvan and satirlar_ust:
        ilk = satirlar_ust[0]
        harf = sum(c.isalpha() for c in ilk)
        if harf >= 8 and harf / len(ilk) > 0.6 and not bizim_mi(ilk) and not re.search(r"IRSAL|FATURA", ilk.upper().replace("İ", "I")):
            unvan = ilk
    if unvan:
        unvan = re.sub(r"^(SAYIN|ALICI|GÖNDEREN|SATICI)\s*[:.]?", "", unvan, flags=re.I).strip(" :")
        bulgu["gonderen"]["unvan"] = unvan

    # --- il (sık geçen iller)
    for il in ("BURDUR", "ISPARTA", "ANTALYA", "DENİZLİ", "AFYON", "İSTANBUL", "ANKARA", "İZMİR", "KONYA", "BURSA"):
        if il.replace("İ", "I") in ust:
            bulgu["gonderen"]["il"] = il.title().replace("İ", "İ")
            break

    # --- ürün satırları (kaba): "ÜRÜN ADI ... 12 ADET" kalıbı
    for satir in duz.splitlines():
        m = re.search(r"^(.*?[A-Za-zÇĞİÖŞÜçğıöşü]{3}.*?)\s+(\d+(?:[.,]\d+)?)\s*(ADET|AD|ADT|KG|LT|L[İI]TRE|MT|METRE|M2|KOL[İI]|KUTU|PAKET|PK|SET|TAKIM)\b",
                      satir, re.I)
        if m and not re.search(r"TOPLAM|TUTAR|KDV|TAR[İI]H", m.group(1), re.I):
            ad = re.sub(r"^[^A-Za-zÇĞİÖŞÜçğıöşü0-9]*\d{0,3}[\s.)-]*[^A-Za-zÇĞİÖŞÜçğıöşü0-9]*", "", m.group(1))
            ad = re.sub(r"(\s+[^\d\s]{1,2})+$", "", ad).strip(" .:-")
            ad = re.sub(r"\s{2,}", " ", ad)
            if len(ad) >= 3:
                birim = m.group(3).upper().replace("İ", "I")
                bulgu["satirlar"].append({"ad": ad[:120], "miktar": _sayi_tr(m.group(2)) or 1,
                                          "birim": BIRIM_ESLE.get(birim, BIRIM_ESLE.get(birim.replace("I", "İ"), "C62")),
                                          "birim_fiyat": None, "kdv": None})

    # --- genel toplam (faturalar için)
    m = re.search(r"(?:GENEL\s*TOPLAM|ÖDENECEK\s*TUTAR|ODENECEK\s*TUTAR)\s*[:.]?\s*([\d.,]+)", ust)
    if m:
        bulgu["genel_toplam"] = _sayi_tr(m.group(1))

    eksik = [ad for ad, deger in (("belge no", bulgu["belge_no"]), ("tarih", bulgu["tarih"]),
                                  ("VKN", bulgu["gonderen"].get("vkn"))) if not deger]
    bulgu["okunamayan"] = ("Okunamadı: " + ", ".join(eksik)) if eksik else ""
    return bulgu


def belge_oku(fotolar, ayarlar):
    """Ayarlardaki yönteme göre okur. (bulgu, ham_metin) döndürür."""
    yontem = ayarlar.get("okuma_yontemi") or "ocr"
    if yontem == "ai":
        return oku(fotolar, ayarlar.get("claude_api_anahtari"), ayarlar.get("claude_model")), ""
    metin = ocr_metin(fotolar, ayarlar.get("tesseract_yolu"))
    return ayikla(metin, (ayarlar.get("firma_vkn") or "").strip(), ayarlar.get("firma_unvan") or ""), metin
