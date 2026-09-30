"""Cariler (müşteri ve tedarikçiler)."""
from datetime import datetime

from fastapi import APIRouter

from .. import entegrator
from ..core import db
from ..core.ortak import hata
from .cari_hesap import cari_bakiyeleri

router = APIRouter()


# ------------------------------------------------------------------ cariler
CARI_ALANLARI = ["unvan", "vkn", "vergi_dairesi", "ad", "soyad", "adres", "ilce", "il", "ulke",
                 "telefon", "eposta", "notlar", "tur", "vade_gun"]


def _cari_dogrula(v):
    if v.get("tur") not in ("musteri", "tedarikci", "ikisi"):
        v["tur"] = "musteri"
    if not (v.get("unvan") or "").strip():
        hata("Ünvan / ad soyad boş olamaz.")
    try:
        gun = int(str(v.get("vade_gun") or 0).strip() or 0)
    except ValueError:
        gun = -1
    if not 0 <= gun <= 365:
        hata("Vade günü 0 ile 365 arasında bir sayı olmalı.")
    v["vade_gun"] = str(gun)
    vkn = (v.get("vkn") or "").strip()
    if vkn and (not vkn.isdigit() or len(vkn) not in (10, 11)):
        hata("VKN 10, TCKN 11 haneli olmalı.")


@router.get("/api/cariler")
def cariler(q: str = "", tur: str = ""):
    sql, p = "SELECT * FROM cariler WHERE (unvan LIKE ? OR vkn LIKE ?)", [f"%{q}%", f"%{q}%"]
    if tur in ("musteri", "tedarikci"):
        sql += " AND tur IN (?, 'ikisi')"
        p.append(tur)
    with db.islem() as con:
        rows = con.execute(sql + " ORDER BY unvan COLLATE NOCASE", p).fetchall()
        b = cari_bakiyeleri(con)
    return [{**dict(r), "bakiye": b.get(r["id"], 0)} for r in rows]


@router.post("/api/cariler")
def cari_ekle(v: dict):
    _cari_dogrula(v)
    with db.islem() as con:
        cur = con.execute(
            f"INSERT INTO cariler({','.join(CARI_ALANLARI)}) VALUES({','.join('?' * len(CARI_ALANLARI))})",
            [(v.get(k) or "").strip() for k in CARI_ALANLARI])
        return dict(con.execute("SELECT * FROM cariler WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/api/cariler/{cid}")
def cari_guncelle(cid: int, v: dict):
    _cari_dogrula(v)
    with db.islem() as con:
        eski = con.execute("SELECT vkn FROM cariler WHERE id=?", (cid,)).fetchone()
        if not eski:
            hata("Müşteri bulunamadı.", 404)
        con.execute(f"UPDATE cariler SET {','.join(k + '=?' for k in CARI_ALANLARI)} WHERE id=?",
                    [(v.get(k) or "").strip() for k in CARI_ALANLARI] + [cid])
        if eski["vkn"] != (v.get("vkn") or "").strip():
            con.execute("UPDATE cariler SET efatura_mukellefi=0, posta_kutusu=NULL, mukellef_sorgu=NULL WHERE id=?", (cid,))
        return dict(con.execute("SELECT * FROM cariler WHERE id=?", (cid,)).fetchone())


@router.delete("/api/cariler/{cid}")
def cari_sil(cid: int):
    with db.islem() as con:
        if con.execute("SELECT 1 FROM faturalar WHERE cari_id=? AND durum!='TASLAK'", (cid,)).fetchone() or \
                con.execute("SELECT 1 FROM gelen_faturalar WHERE cari_id=?", (cid,)).fetchone() or \
                con.execute("SELECT 1 FROM irsaliyeler WHERE cari_id=?", (cid,)).fetchone() or \
                con.execute("SELECT 1 FROM hareketler WHERE cari_id=?", (cid,)).fetchone():
            hata("Bu cariye ait fatura, irsaliye veya ödeme kaydı olduğu için silinemez.")
        con.execute("DELETE FROM cariler WHERE id=?", (cid,))
    return {"ok": True}


@router.get("/api/cariler/{cid}")
def cari(cid: int):
    with db.islem() as con:
        r = con.execute("SELECT * FROM cariler WHERE id=?", (cid,)).fetchone()
        if not r:
            hata("Cari bulunamadı.", 404)
        return {**dict(r), "bakiye": cari_bakiyeleri(con).get(cid, 0)}


@router.post("/api/cariler/{cid}/mukellef-sorgula")
def mukellef_sorgula(cid: int):
    with db.islem() as con:
        c = con.execute("SELECT * FROM cariler WHERE id=?", (cid,)).fetchone()
    if not c:
        hata("Müşteri bulunamadı.", 404)
    if not c["vkn"]:
        hata("Sorgu için önce VKN/TCKN girin.")
    mukellef, etiket = entegrator.istemci(db.ayarlar_hepsi()).efatura_mukellefi_mi(c["vkn"])
    with db.islem() as con:
        con.execute("UPDATE cariler SET efatura_mukellefi=?, posta_kutusu=?, mukellef_sorgu=? WHERE id=?",
                    (int(mukellef), etiket, datetime.now().isoformat(timespec="minutes"), cid))
        return dict(con.execute("SELECT * FROM cariler WHERE id=?", (cid,)).fetchone())


