"""Lisans: internetsiz doğrulanan, imzalı lisans anahtarı.

Anahtar biçimi: <base64 JSON>.<base64 Ed25519 imzası>
JSON: {"no", "musteri", "bitis": "YYYY-AA-GG", "firma": int, "kullanici": int, "makine": "" | makine kodu}
İmzalamak için tools/lisans_uret.py ve SİZDE kalan özel anahtar kullanılır; programda yalnızca açık anahtar vardır.
Lisans yoksa kurulumdan itibaren DENEME_GUN gün tam deneme; süre bitince program salt okumaya geçer
(veriler görülebilir ve dışa aktarılabilir, yeni kayıt yapılamaz).
"""
import base64
import hashlib
import json
import os
import platform
from datetime import date, timedelta

from . import db

ACIK_ANAHTAR_B64 = "enRMaXT9VyK4hhNEZC8gr20GDeJzgGjCRJyq-iF47LA"
DENEME_GUN = 30
DENEME_SINIR = {"firma": 2, "kullanici": 3}


def makine_kodu():
    """Bu bilgisayara özgü kısa kod (lisansı bilgisayara bağlamak için)."""
    ham = ""
    try:
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                ham = winreg.QueryValueEx(k, "MachineGuid")[0]
        elif os.path.isfile("/etc/machine-id"):
            ham = open("/etc/machine-id").read().strip()
    except OSError:
        pass
    ham = ham or platform.node()
    h = hashlib.sha256(("efatura:" + ham).encode()).hexdigest().upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def coz(anahtar):
    """Anahtarı doğrular, içeriği döndürür; geçersizse ValueError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        govde, imza = anahtar.strip().split(".")
        Ed25519PublicKey.from_public_bytes(_b64(ACIK_ANAHTAR_B64)).verify(_b64(imza), govde.encode())
        veri = json.loads(_b64(govde))
    except (ValueError, InvalidSignature, TypeError):
        raise ValueError("Lisans anahtarı geçersiz.")
    if veri.get("makine") and veri["makine"] != makine_kodu():
        raise ValueError("Bu lisans başka bir bilgisayar için verilmiş.")
    return veri


def _sistem_ayar(anahtar, deger=None):
    with db.sistem() as con:
        if deger is not None:
            con.execute("INSERT INTO ayarlar(anahtar, deger) VALUES(?,?) "
                        "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger", (anahtar, deger))
            return deger
        r = con.execute("SELECT deger FROM ayarlar WHERE anahtar=?", (anahtar,)).fetchone()
        return r["deger"] if r else None


def durum():
    """{'tur': 'lisans'|'deneme', 'gecerli', 'bitis', 'kalan_gun', 'firma', 'kullanici', 'musteri', 'makine'}"""
    bugun = date.today()
    anahtar = _sistem_ayar("lisans_anahtari")
    if anahtar:
        try:
            v = coz(anahtar)
            bitis = date.fromisoformat(v["bitis"])
            return {"tur": "lisans", "gecerli": bitis >= bugun, "bitis": v["bitis"], "kalan_gun": (bitis - bugun).days,
                    "firma": int(v.get("firma", 1)), "kullanici": int(v.get("kullanici", 1)),
                    "musteri": v.get("musteri", ""), "no": v.get("no", ""), "makine": makine_kodu()}
        except (ValueError, KeyError):
            pass
    kurulum = _sistem_ayar("kurulum_tarihi") or _sistem_ayar("kurulum_tarihi", bugun.isoformat())
    bitis = date.fromisoformat(kurulum) + timedelta(days=DENEME_GUN)
    return {"tur": "deneme", "gecerli": bitis >= bugun, "bitis": bitis.isoformat(), "kalan_gun": (bitis - bugun).days,
            **DENEME_SINIR, "musteri": "", "no": "", "makine": makine_kodu()}


def yukle(anahtar):
    v = coz(anahtar)
    if date.fromisoformat(v["bitis"]) < date.today():
        raise ValueError("Bu lisansın süresi dolmuş.")
    _sistem_ayar("lisans_anahtari", anahtar.strip())
    return durum()
