"""Sistem: ilk kurulum, giriş/çıkış, kullanıcılar, firmalar, firma seçimi, lisans."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..core import db, gocler, guvenlik, lisans, yetki
from ..core.guvenlik import oturum
from ..core.ortak import hata
from ..core.yapilandirma import SURUM
from ..servisler.ubl import BIRIMLER, PARA_BIRIMLERI, TEVKIFAT_KODLARI

acik = APIRouter()                                   # oturum gerektirmeyenler
router = APIRouter(dependencies=[Depends(oturum)])   # oturum + yetki denetimli


def _kurulu():
    with db.sistem() as con:
        return bool(con.execute("SELECT 1 FROM kullanicilar").fetchone())


def _sabitler():
    return {"birimler": BIRIMLER, "para_birimleri": PARA_BIRIMLERI,
            "tevkifat": {k: {"ad": v[0], "pay": v[1]} for k, v in TEVKIFAT_KODLARI.items()},
            "roller": {k: v["ad"] for k, v in yetki.ROLLER.items()}, "surum": SURUM}


@acik.get("/api/durum")
def durum():
    return {"kurulum_gerekli": not _kurulu(), **_sabitler()}


@acik.post("/api/kurulum")
def ilk_kurulum(v: dict, request: Request, response: Response):
    """İlk açılış: sistem yöneticisi ve ilk firma."""
    if _kurulu():
        hata("Program zaten kurulmuş.")
    kadi = (v.get("kullanici_adi") or "").strip()
    if not re.match(r"^[\w.\-]{3,40}$", kadi):
        hata("Kullanıcı adı 3-40 karakter olmalı; harf, rakam, nokta, tire kullanın.")
    guvenlik.sifre_kontrol(v.get("sifre"))
    unvan = (v.get("firma_unvan") or "").strip()
    if not unvan:
        hata("Firma ünvanını girin.")
    with db.sistem() as con:
        fid = con.execute("INSERT INTO firmalar(unvan) VALUES(?)", (unvan,)).lastrowid
        kid = con.execute("INSERT INTO kullanicilar(kullanici_adi, ad, sifre_hash, sistem_yoneticisi) VALUES(?,?,?,1)",
                          (kadi, (v.get("ad") or kadi).strip(), guvenlik.sifre_hash(v["sifre"]))).lastrowid
        con.execute("INSERT INTO firma_yetkileri(kullanici_id, firma_id, rol) VALUES(?,?,'yonetici')", (kid, fid))
    gocler.firma_hazirla(fid)
    with db.firma_baglami(fid):
        db.ayar_yaz({"firma_unvan": unvan, "firma_ulke": "Türkiye", "seri_efatura": "EFT", "seri_earsiv": "EAR"})
    lisans.durum()  # deneme süresini başlat
    guvenlik.oturum_ac(response, request, kid, fid)
    return {"ok": True}


@acik.post("/api/giris")
def giris(v: dict, request: Request, response: Response):
    kadi = (v.get("kullanici_adi") or "").strip()
    anahtar = (request.client.host if request.client else "?", kadi.lower())
    sayi = guvenlik.giris_kilidi(anahtar)
    with db.sistem() as con:
        k = con.execute("SELECT * FROM kullanicilar WHERE kullanici_adi=? AND aktif=1", (kadi,)).fetchone()
        firmalar = guvenlik.kullanici_firmalari(con, k["id"]) if k else []
    if not k or not guvenlik.sifre_dogru(v.get("sifre", ""), k["sifre_hash"]):
        guvenlik.hatali_giris(anahtar, sayi)
    if not firmalar and not k["sistem_yoneticisi"]:
        hata("Hesabınıza bağlı bir firma yok. Yöneticinize başvurun.", 403)
    guvenlik.GIRIS_DENEMELERI.pop(anahtar, None)
    guvenlik.oturum_ac(response, request, k["id"], firmalar[0]["id"] if firmalar else None)
    return {"ok": True}


@acik.post("/api/cikis")
def cikis(request: Request, response: Response):
    with db.sistem() as con:
        con.execute("DELETE FROM oturumlar WHERE token=?", (request.cookies.get("oturum", ""),))
    response.delete_cookie("oturum")
    return {"ok": True}


# ------------------------------------------------------------------ oturum bilgisi, firma seçimi, şifre
@router.get("/api/ben")
def ben(request: Request):
    k = request.state.kullanici
    with db.sistem() as con:
        firmalar = guvenlik.kullanici_firmalari(con, k["id"])
    aktif = next((f for f in firmalar if f["id"] == k["firma_id"]), None)
    mod = None
    if aktif:
        with db.firma_baglami(aktif["id"]):
            a = db.ayarlar_hepsi()
        mod = "deneme" if (a.get("entegrator") or "deneme") == "deneme" else (a.get("ent_ortam") or "test")
    return {"kullanici": {x: k[x] for x in ("id", "kullanici_adi", "ad", "sistem_yoneticisi", "rol")},
            "izinler": k["izinler"], "firma": aktif, "firmalar": firmalar, "mod": mod,
            "lisans": lisans.durum(), **_sabitler()}


@router.post("/api/firma-sec")
def firma_sec(v: dict, request: Request):
    k = request.state.kullanici
    with db.sistem() as con:
        izinli = {f["id"] for f in guvenlik.kullanici_firmalari(con, k["id"])}
        if v.get("firma_id") not in izinli:
            hata("Bu firmaya erişim yetkiniz yok.", 403)
        con.execute("UPDATE oturumlar SET firma_id=? WHERE token=?", (v["firma_id"], k["token"]))
    return {"ok": True}


@router.post("/api/sifre")
def sifre_degistir(v: dict, request: Request):
    k = request.state.kullanici
    with db.sistem() as con:
        kayit = con.execute("SELECT sifre_hash FROM kullanicilar WHERE id=?", (k["id"],)).fetchone()
        if not guvenlik.sifre_dogru(v.get("eski", ""), kayit["sifre_hash"]):
            hata("Mevcut şifre yanlış.")
        guvenlik.sifre_kontrol(v.get("yeni"))
        con.execute("UPDATE kullanicilar SET sifre_hash=? WHERE id=?", (guvenlik.sifre_hash(v["yeni"]), k["id"]))
        con.execute("DELETE FROM oturumlar WHERE kullanici_id=? AND token!=?", (k["id"], k["token"]))
    return {"ok": True}


# ------------------------------------------------------------------ kullanıcılar (sistem yöneticisi)
def _kullanici_listesi(con):
    liste = []
    for k in con.execute("SELECT id, kullanici_adi, ad, sistem_yoneticisi, aktif, son_giris FROM kullanicilar "
                         "ORDER BY kullanici_adi COLLATE NOCASE"):
        d = dict(k)
        d["yetkiler"] = [dict(y) for y in con.execute(
            "SELECT firma_id, rol FROM firma_yetkileri WHERE kullanici_id=?", (k["id"],))]
        liste.append(d)
    return liste


def _yetkileri_yaz(con, kid, yetkiler):
    firmalar = {r["id"] for r in con.execute("SELECT id FROM firmalar")}
    con.execute("DELETE FROM firma_yetkileri WHERE kullanici_id=?", (kid,))
    for y in yetkiler or []:
        if y.get("rol") in yetki.ROLLER and y.get("firma_id") in firmalar:
            con.execute("INSERT INTO firma_yetkileri(kullanici_id, firma_id, rol) VALUES(?,?,?)",
                        (kid, y["firma_id"], y["rol"]))


def _sistem_yoneticisi_kalir_mi(con, haric_id):
    return bool(con.execute("SELECT 1 FROM kullanicilar WHERE sistem_yoneticisi=1 AND aktif=1 AND id!=?",
                            (haric_id,)).fetchone())


@router.get("/api/kullanicilar")
def kullanicilar():
    with db.sistem() as con:
        return _kullanici_listesi(con)


@router.post("/api/kullanicilar")
def kullanici_ekle(v: dict):
    kadi = (v.get("kullanici_adi") or "").strip()
    if not re.match(r"^[\w.\-]{3,40}$", kadi):
        hata("Kullanıcı adı 3-40 karakter olmalı; harf, rakam, nokta, tire kullanın.")
    guvenlik.sifre_kontrol(v.get("sifre"))
    with db.sistem() as con:
        aktif_sayi = con.execute("SELECT COUNT(*) FROM kullanicilar WHERE aktif=1").fetchone()[0]
        if aktif_sayi >= lisans.durum()["kullanici"]:
            hata(f"Lisansınız en fazla {lisans.durum()['kullanici']} kullanıcıya izin veriyor.")
        if con.execute("SELECT 1 FROM kullanicilar WHERE kullanici_adi=?", (kadi,)).fetchone():
            hata("Bu kullanıcı adı kullanılıyor.")
        kid = con.execute("INSERT INTO kullanicilar(kullanici_adi, ad, sifre_hash, sistem_yoneticisi) VALUES(?,?,?,?)",
                          (kadi, (v.get("ad") or kadi).strip(), guvenlik.sifre_hash(v["sifre"]),
                           1 if v.get("sistem_yoneticisi") else 0)).lastrowid
        _yetkileri_yaz(con, kid, v.get("yetkiler"))
        return next(k for k in _kullanici_listesi(con) if k["id"] == kid)


@router.put("/api/kullanicilar/{kid}")
def kullanici_guncelle(kid: int, v: dict, request: Request):
    with db.sistem() as con:
        if not con.execute("SELECT 1 FROM kullanicilar WHERE id=?", (kid,)).fetchone():
            hata("Kullanıcı bulunamadı.", 404)
        aktif = 1 if v.get("aktif", True) else 0
        yonetici = 1 if v.get("sistem_yoneticisi") else 0
        if (not aktif or not yonetici) and not _sistem_yoneticisi_kalir_mi(con, kid):
            hata("En az bir etkin sistem yöneticisi kalmalı.")
        con.execute("UPDATE kullanicilar SET ad=?, aktif=?, sistem_yoneticisi=? WHERE id=?",
                    ((v.get("ad") or "").strip(), aktif, yonetici, kid))
        if v.get("sifre"):
            guvenlik.sifre_kontrol(v["sifre"])
            con.execute("UPDATE kullanicilar SET sifre_hash=? WHERE id=?", (guvenlik.sifre_hash(v["sifre"]), kid))
        if v.get("sifre") or not aktif:
            con.execute("DELETE FROM oturumlar WHERE kullanici_id=? AND token!=?", (kid, request.state.kullanici["token"]))
        if "yetkiler" in v:
            _yetkileri_yaz(con, kid, v["yetkiler"])
        return next(k for k in _kullanici_listesi(con) if k["id"] == kid)


# ------------------------------------------------------------------ firmalar (sistem yöneticisi)
@router.get("/api/firmalar")
def firmalar():
    with db.sistem() as con:
        return [dict(r) for r in con.execute("SELECT * FROM firmalar ORDER BY unvan COLLATE NOCASE")]


@router.post("/api/firmalar")
def firma_ekle(v: dict, request: Request):
    unvan = (v.get("unvan") or "").strip()
    if not unvan:
        hata("Firma ünvanını girin.")
    with db.sistem() as con:
        sayi = con.execute("SELECT COUNT(*) FROM firmalar WHERE aktif=1").fetchone()[0]
        if sayi >= lisans.durum()["firma"]:
            hata(f"Lisansınız en fazla {lisans.durum()['firma']} firmaya izin veriyor.")
        fid = con.execute("INSERT INTO firmalar(unvan) VALUES(?)", (unvan,)).lastrowid
        con.execute("INSERT INTO firma_yetkileri(kullanici_id, firma_id, rol) VALUES(?,?,'yonetici')",
                    (request.state.kullanici["id"], fid))
    gocler.firma_hazirla(fid)
    with db.firma_baglami(fid):
        db.ayar_yaz({"firma_unvan": unvan, "firma_ulke": "Türkiye", "seri_efatura": "EFT", "seri_earsiv": "EAR"})
    return {"id": fid, "unvan": unvan}


@router.put("/api/firmalar/{fid}")
def firma_guncelle(fid: int, v: dict, request: Request):
    with db.sistem() as con:
        if not con.execute("SELECT 1 FROM firmalar WHERE id=?", (fid,)).fetchone():
            hata("Firma bulunamadı.", 404)
        if "aktif" in v and not v["aktif"] and fid == request.state.kullanici["firma_id"]:
            hata("Şu an açık olan firmayı pasifleştiremezsiniz; önce başka firmaya geçin.")
        if "aktif" in v:
            con.execute("UPDATE firmalar SET aktif=? WHERE id=?", (1 if v["aktif"] else 0, fid))
    return {"ok": True}


# ------------------------------------------------------------------ lisans (sistem yöneticisi)
@router.get("/api/lisans")
def lisans_durumu():
    return lisans.durum()


@router.post("/api/lisans")
def lisans_gir(v: dict):
    try:
        return lisans.yukle(v.get("anahtar") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
