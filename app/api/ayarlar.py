"""Firma ayarları, döviz kuru, erişim bilgisi, entegratör testi, yedek, günlük, tarama."""
import io
import json
import os
import re
from datetime import datetime

from fastapi import APIRouter, Response

from .. import entegrator
from ..core import db
from ..core.ortak import FIRMA_ALANLARI, hata
from ..servisler.okuma import tesseract_bul
from ..servisler.ubl import PARA_BIRIMLERI

router = APIRouter()


from ..servisler.tarama import tarama_yap

# ------------------------------------------------------------------ ayarlar
GIZLI_AYARLAR = {"ent_sifre", "claude_api_anahtari"}
SERBEST_AYARLAR = {"seri_efatura", "seri_earsiv", "entegrator", "ent_ortam", "okuma_yontemi", "tesseract_yolu",
                   "claude_model", "tarama_saati"}


@router.get("/api/ayarlar")
def ayarlar_getir():
    a = db.ayarlar_hepsi()
    sonuc = {k: v for k, v in a.items() if k not in GIZLI_AYARLAR}
    sonuc["ent_sifre_var"] = bool(a.get("ent_sifre"))
    sonuc["claude_anahtar_var"] = bool(a.get("claude_api_anahtari"))
    sonuc["veri_klasoru"] = db.firma_dizini()
    sonuc["tesseract_bulundu"] = bool(tesseract_bul(a.get("tesseract_yolu")))
    return sonuc


@router.put("/api/ayarlar")
def ayarlar_kaydet(veri: dict):
    ent_alanlari = {al["anahtar"] for s in entegrator.KAYIT.values() for al in s.alanlar}
    izinli = {"firma_" + k for k in FIRMA_ALANLARI} | SERBEST_AYARLAR | (ent_alanlari - GIZLI_AYARLAR)
    yeni = {k: str(v or "").strip()[:500] for k, v in veri.items() if k in izinli}
    for s in ("seri_efatura", "seri_earsiv"):
        if s in yeni:
            yeni[s] = yeni[s].upper()
            if len(yeni[s]) != 3 or not yeni[s].isalnum():
                hata("Fatura serisi tam 3 harf/rakam olmalı (ör. IYG).")
    if "entegrator" in yeni and yeni["entegrator"] not in entegrator.KAYIT:
        hata("Geçersiz entegratör.")
    if "ent_ortam" in yeni and yeni["ent_ortam"] not in ("test", "canli"):
        hata("Geçersiz ortam.")
    if yeni.get("okuma_yontemi") and yeni["okuma_yontemi"] not in ("ocr", "ai"):
        hata("Geçersiz okuma yöntemi.")
    if yeni.get("tarama_saati") and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", yeni["tarama_saati"]):
        hata("Tarama saati SS:DD biçiminde olmalı (ör. 09:00).")
    if yeni.get("firma_vkn") and (not yeni["firma_vkn"].isdigit() or len(yeni["firma_vkn"]) not in (10, 11)):
        hata("Firma VKN 10, TCKN 11 haneli olmalı.")
    for gizli in GIZLI_AYARLAR:
        if veri.get(gizli):
            yeni[gizli] = str(veri[gizli]).strip()
    db.ayar_yaz(yeni)
    if yeni.get("firma_unvan"):
        with db.sistem() as con:
            con.execute("UPDATE firmalar SET unvan=? WHERE id=?", (yeni["firma_unvan"], db.aktif_firma_id()))
    return ayarlar_getir()


# ------------------------------------------------------------------ döviz kuru (TCMB)
@router.get("/api/kur")
def tcmb_kur(para: str, tarih: str = ""):
    """TCMB'nin ilgili gün (tatilse önceki iş günü) döviz alış kurunu getirir."""
    import requests
    from datetime import date, timedelta
    if para not in PARA_BIRIMLERI or para == "TRY":
        hata("Geçersiz para birimi.")
    try:
        gun = date.fromisoformat(tarih) if tarih else date.today()
    except ValueError:
        hata("Geçersiz tarih.")
    from defusedxml.ElementTree import fromstring as guvenli_xml
    from xml.etree.ElementTree import ParseError
    for _ in range(7):
        url = ("https://www.tcmb.gov.tr/kurlar/today.xml" if gun == date.today()
               else f"https://www.tcmb.gov.tr/kurlar/{gun:%Y%m}/{gun:%d%m%Y}.xml")
        try:
            r = requests.get(url, timeout=10)
        except requests.RequestException:
            hata("TCMB'ye bağlanılamadı. Kuru elle girin.", 502)
        if r.status_code == 200:
            try:
                kok = guvenli_xml(r.content)
            except ParseError:
                break
            for c in kok.iter("Currency"):
                if c.get("Kod") == para or c.get("CurrencyCode") == para:
                    deger = (c.findtext("ForexBuying") or "").strip()
                    if deger:
                        return {"para": para, "kur": float(deger), "tarih": gun.isoformat(),
                                "kaynak": "TCMB döviz alış kuru"}
            break
        gun -= timedelta(days=1)
    hata("Bu tarih için TCMB kuru bulunamadı. Kuru elle girin.", 404)


# ------------------------------------------------------------------ uzaktan erişim bilgisi
@router.get("/api/erisim")
def erisim_bilgisi():
    """Bu bilgisayarın yerel ağ adresleri ve (kuruluysa) Tailscale adresi."""
    import shutil
    import socket
    import subprocess
    yerel = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        yerel.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for bilgi in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not bilgi[4][0].startswith("127."):
                yerel.add(bilgi[4][0])
    except OSError:
        pass
    ts = {"kurulu": False}
    yol = shutil.which("tailscale") or next((p for p in (r"C:\Program Files\Tailscale\tailscale.exe",)
                                              if os.path.isfile(p)), None)
    if yol:
        ts["kurulu"] = True
        try:
            cikti = subprocess.run([yol, "status", "--json"], capture_output=True, timeout=5, text=True)
            durum = json.loads(cikti.stdout or "{}")
            ben = durum.get("Self") or {}
            ts["bagli"] = durum.get("BackendState") == "Running"
            ts["ad"] = (ben.get("DNSName") or "").rstrip(".")
            ts["ip"] = (ben.get("TailscaleIPs") or [None])[0]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            ts["bagli"] = False
    return {"yerel": sorted(yerel), "port": 8000, "tailscale": ts}


# ------------------------------------------------------------------ entegratör
@router.get("/api/entegratorler")
def entegratorler():
    return entegrator.liste()


@router.post("/api/entegrator-test")
def entegrator_testi():
    """Seçili entegratöre bağlanıp giriş, mükellef sorgusu ve gelen fatura listelemeyi dener."""
    ayar = db.ayarlar_hepsi()
    ist = entegrator.istemci(ayar)
    if ist.kod == "deneme":
        hata("Deneme modundasınız. Ayarlar'da gerçek entegratörü ve test ortamını seçip kaydedin, sonra tekrar deneyin.")
    if not ayar.get("firma_vkn"):
        hata("Önce firma VKN'nizi girin.")
    adimlar = ist.baglanti_testi()
    db.gunluge_yaz(f"{ist.ad} bağlantı testi ({ist.mod}): " +
                   ", ".join(f"{x['ad']}: {'tamam' if x['ok'] else 'HATA'}" for x in adimlar))
    return {"entegrator": ist.ad, "mod": ist.mod, "adimlar": adimlar}


# ------------------------------------------------------------------ yedek
@router.get("/api/yedek")
def yedek_al():
    """Veritabanının tutarlı bir kopyası + belge fotoğrafları, tek zip dosyası."""
    import sqlite3
    import tempfile
    import zipfile
    with tempfile.TemporaryDirectory() as gecici:
        kopya = os.path.join(gecici, "fatura.db")
        kaynak = db.baglan()
        hedef = sqlite3.connect(kopya)
        kaynak.backup(hedef)
        hedef.close()
        kaynak.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(kopya, "veri/fatura.db")
            if os.path.isdir(db.belge_dizini()):
                for ad in os.listdir(db.belge_dizini()):
                    z.write(os.path.join(db.belge_dizini(), ad), f"veri/belgeler/{ad}")
    db.ayar_yaz({"son_yedek": datetime.now().isoformat(timespec="minutes")})
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="efatura_yedek_{datetime.now():%Y%m%d_%H%M}.zip"'})


# ------------------------------------------------------------------ tarama ve zamanlayıcı
@router.post("/api/tarama")
def tarama():
    return tarama_yap()


@router.get("/api/gunluk")
def gunluk():
    with db.islem() as con:
        return [dict(r) for r in con.execute("SELECT * FROM gunluk ORDER BY id DESC LIMIT 30")]
