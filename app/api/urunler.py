"""Ürün kartları."""

from fastapi import APIRouter

from ..core import db
from ..core.ortak import hata

router = APIRouter()


# ------------------------------------------------------------------ ürünler
@router.get("/api/urunler")
def urunler():
    with db.islem() as con:
        return [dict(r) for r in con.execute("SELECT * FROM urunler WHERE aktif=1 ORDER BY ad COLLATE NOCASE")]


def _urun_alanlar(v):
    if not (v.get("ad") or "").strip():
        hata("Ürün/hizmet adı boş olamaz.")
    try:
        return [v["ad"].strip(), (v.get("kod") or "").strip(), v.get("birim") or "C62",
                float(v.get("fiyat") or 0), float(v.get("kdv") if v.get("kdv") not in (None, "") else 20),
                1 if str(v.get("stok_takibi", "1")) in ("1", "true", "on") else 0,
                float(v.get("kritik") or 0), float(v["alis_fiyat"]) if v.get("alis_fiyat") not in (None, "") else None]
    except ValueError:
        hata("Fiyat, KDV ve kritik seviye rakam olmalı.")


@router.post("/api/urunler")
def urun_ekle(v: dict):
    with db.islem() as con:
        cur = con.execute("INSERT INTO urunler(ad,kod,birim,fiyat,kdv,stok_takibi,kritik,alis_fiyat) VALUES(?,?,?,?,?,?,?,?)",
                          _urun_alanlar(v))
        return dict(con.execute("SELECT * FROM urunler WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/api/urunler/{uid}")
def urun_guncelle(uid: int, v: dict):
    with db.islem() as con:
        con.execute("UPDATE urunler SET ad=?,kod=?,birim=?,fiyat=?,kdv=?,stok_takibi=?,kritik=?,alis_fiyat=? WHERE id=?",
                    _urun_alanlar(v) + [uid])
        return dict(con.execute("SELECT * FROM urunler WHERE id=?", (uid,)).fetchone())


@router.delete("/api/urunler/{uid}")
def urun_sil(uid: int):
    with db.islem() as con:
        con.execute("UPDATE urunler SET aktif=0 WHERE id=?", (uid,))
    return {"ok": True}


