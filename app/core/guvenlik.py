"""Kimlik doğrulama, oturumlar ve her istekte yetki denetimi."""
import hashlib
import secrets
import time

from fastapi import HTTPException, Request

from . import db, lisans, yetki

OTURUM_GUN = 30
GIRIS_DENEMELERI = {}  # (ip, kullanıcı adı) -> [hatalı deneme, kilit bitişi]


def sifre_hash(sifre, tuz=None):
    tuz = tuz or secrets.token_hex(16)
    return tuz + "$" + hashlib.pbkdf2_hmac("sha256", sifre.encode(), tuz.encode(), 200_000).hex()


def sifre_dogru(sifre, kayitli):
    return secrets.compare_digest(sifre_hash(sifre, kayitli.split("$", 1)[0]), kayitli)


def sifre_kontrol(sifre):
    if len(sifre or "") < 8:
        raise HTTPException(400, "Şifre en az 8 karakter olmalı.")


def giris_kilidi(anahtar):
    sayi, kilit = GIRIS_DENEMELERI.get(anahtar, [0, 0])
    if kilit > time.time():
        raise HTTPException(429, f"Çok fazla hatalı deneme. {int((kilit - time.time()) // 60) + 1} dakika sonra tekrar deneyin.")
    return sayi


def hatali_giris(anahtar, sayi):
    sayi += 1
    GIRIS_DENEMELERI[anahtar] = [0, time.time() + 15 * 60] if sayi >= 5 else [sayi, 0]
    kalan = 5 - sayi
    raise HTTPException(401, "Kullanıcı adı veya şifre yanlış." + (f" {kalan} deneme hakkınız kaldı." if 0 < kalan <= 3 else ""))


def oturum_ac(response, request, kullanici_id, firma_id):
    token = secrets.token_urlsafe(32)
    with db.sistem() as con:
        con.execute("DELETE FROM oturumlar WHERE olusturma < datetime('now', ?)", (f"-{OTURUM_GUN} days",))
        con.execute("INSERT INTO oturumlar(token, kullanici_id, firma_id) VALUES(?,?,?)", (token, kullanici_id, firma_id))
        con.execute("UPDATE kullanicilar SET son_giris=datetime('now') WHERE id=?", (kullanici_id,))
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"
    response.set_cookie("oturum", token, httponly=True, samesite="strict", secure=https, max_age=OTURUM_GUN * 86400)


def kullanici_firmalari(con, kullanici_id):
    return [dict(r) for r in con.execute(
        "SELECT f.id, f.unvan, y.rol FROM firma_yetkileri y JOIN firmalar f ON f.id=y.firma_id "
        "WHERE y.kullanici_id=? AND f.aktif=1 ORDER BY f.unvan COLLATE NOCASE", (kullanici_id,))]


async def oturum(request: Request):
    """Her korumalı istekte çalışır: oturum geçerli mi, firma yetkisi var mı, bu işleme izin var mı, lisans uygun mu.
    Geçerliyse aktif firmayı belirler (db.islem() artık o firmanın dosyasını kullanır)."""
    token = request.cookies.get("oturum")
    if not token:
        raise HTTPException(401, "Giriş yapmanız gerekiyor.")
    with db.sistem() as con:
        o = con.execute(
            "SELECT o.firma_id, k.id, k.kullanici_adi, k.ad, k.sistem_yoneticisi, k.aktif FROM oturumlar o "
            "JOIN kullanicilar k ON k.id=o.kullanici_id WHERE o.token=? AND o.olusturma >= datetime('now', ?)",
            (token, f"-{OTURUM_GUN} days")).fetchone()
        if not o or not o["aktif"]:
            raise HTTPException(401, "Oturumunuz sona erdi, tekrar giriş yapın.")
        y = con.execute("SELECT y.rol FROM firma_yetkileri y JOIN firmalar f ON f.id=y.firma_id "
                        "WHERE y.kullanici_id=? AND y.firma_id=? AND f.aktif=1", (o["id"], o["firma_id"])).fetchone()
    rol = y["rol"] if y else None
    izinler = set(yetki.ROLLER.get(rol, {}).get("izinler", set()))
    if o["sistem_yoneticisi"]:
        izinler.add("sistem")
    gerek = yetki.gereken_izin(request.method, request.url.path)
    if gerek is not None and rol is None and gerek != "sistem":
        raise HTTPException(403, "Bu firmaya erişim yetkiniz yok. Başka bir firma seçin.")
    if not yetki.izinli(izinler, gerek):
        raise HTTPException(403, "Bu işlem için yetkiniz yok.")
    if request.method not in ("GET", "HEAD") and gerek not in (None, "sistem") and not lisans.durum()["gecerli"]:
        raise HTTPException(403, "Lisans süresi doldu; program salt okuma modunda. Yönetim > Lisans bölümünden lisans girin.")
    request.state.kullanici = {"id": o["id"], "kullanici_adi": o["kullanici_adi"], "ad": o["ad"],
                               "sistem_yoneticisi": bool(o["sistem_yoneticisi"]), "rol": rol,
                               "izinler": sorted(izinler), "firma_id": o["firma_id"], "token": token}
    if o["firma_id"] is not None and rol is not None:
        db._aktif_firma.set(o["firma_id"])
    return request.state.kullanici
