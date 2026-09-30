"""Stok uç noktaları."""
import json
import re
from datetime import datetime

from fastapi import APIRouter

from ..core import db
from ..core.ortak import hata
from ..servisler.stok import TUR_AD, _k, kaynak_yaz, miktarlar, ortalama_maliyetler, satirlari_bagla, urun_bul

router = APIRouter()


# ------------------------------------------------------------------ uç noktalar
@router.get("/api/stok")
def stok():
    with db.islem() as con:
        m, mal = miktarlar(con), ortalama_maliyetler(con)
        liste = []
        for u in con.execute("SELECT * FROM urunler WHERE aktif=1 ORDER BY ad COLLATE NOCASE"):
            d = dict(u)
            d["miktar"] = m.get(u["id"], 0) if u["stok_takibi"] else None
            d["maliyet"] = _k(mal[u["id"]], 2) if u["id"] in mal else None
            d["deger"] = _k(d["miktar"] * d["maliyet"], 2) if d["miktar"] and d["maliyet"] and d["miktar"] > 0 else 0
            d["kritik_durum"] = bool(u["stok_takibi"] and (u["kritik"] or 0) > 0 and d["miktar"] <= u["kritik"])
            liste.append(d)
        return liste


@router.get("/api/urunler/{uid}/hareketler")
def urun_hareketleri(uid: int):
    with db.islem() as con:
        u = con.execute("SELECT * FROM urunler WHERE id=?", (uid,)).fetchone()
        if not u:
            hata("Ürün bulunamadı.", 404)
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM stok_hareketleri WHERE urun_id=? ORDER BY tarih, id", (uid,))]
    kalan = 0
    for r in rows:
        kalan += r["miktar"]
        r["kalan"] = _k(kalan)
        r["tur_ad"] = TUR_AD.get(r["tur"], r["tur"])
    rows.reverse()
    return {"urun": dict(u), "miktar": _k(kalan), "hareketler": rows}


@router.post("/api/urunler/{uid}/stok-duzelt")
def stok_duzelt(uid: int, v: dict):
    """tur=ACILIS: miktar kadar giriş. tur=SAYIM: sayılan miktara göre fark kaydı."""
    tarih = v.get("tarih") or datetime.now().strftime("%Y-%m-%d")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", tarih):
        hata("Tarihi girin.")
    try:
        miktar = float(str(v.get("miktar")).replace(",", ".")) if v.get("miktar") not in (None, "") else None
    except ValueError:
        miktar = None
    if miktar is None:
        hata("Miktarı rakamla girin.")
    with db.islem() as con:
        if not con.execute("SELECT 1 FROM urunler WHERE id=?", (uid,)).fetchone():
            hata("Ürün bulunamadı.", 404)
        if v.get("tur") == "SAYIM":
            mevcut = miktarlar(con).get(uid, 0)
            fark = _k(miktar - mevcut)
            if abs(fark) < 1e-9:
                return {"ok": True, "fark": 0}
            con.execute("INSERT INTO stok_hareketleri(urun_id,tarih,tur,miktar,kaynak,aciklama) VALUES(?,?,?,?,?,?)",
                        (uid, tarih, "SAYIM", fark, "manuel", v.get("aciklama") or f"Sayılan: {miktar:g}"))
            return {"ok": True, "fark": fark}
        if miktar <= 0:
            hata("Açılış miktarı sıfırdan büyük olmalı.")
        try:
            fiyat = float(str(v.get("birim_fiyat") or "").replace(",", ".")) if v.get("birim_fiyat") else None
        except ValueError:
            fiyat = None
        con.execute("INSERT INTO stok_hareketleri(urun_id,tarih,tur,miktar,birim_fiyat,kaynak,aciklama) VALUES(?,?,?,?,?,?,?)",
                    (uid, tarih, "ACILIS", miktar, fiyat, "manuel", v.get("aciklama") or ""))
        if fiyat:
            con.execute("UPDATE urunler SET alis_fiyat=? WHERE id=?", (fiyat, uid))
    return {"ok": True}


@router.delete("/api/stok-hareketleri/{hid}")
def stok_hareket_sil(hid: int):
    with db.islem() as con:
        r = con.execute("SELECT kaynak FROM stok_hareketleri WHERE id=?", (hid,)).fetchone()
        if not r:
            hata("Kayıt bulunamadı.", 404)
        if r["kaynak"] != "manuel":
            hata("Belgeden gelen stok hareketi silinemez; ilgili irsaliye veya faturayı düzeltin.")
        con.execute("DELETE FROM stok_hareketleri WHERE id=?", (hid,))
    return {"ok": True}


@router.get("/api/gelen/{gid}/stok")
def gelen_stok_durumu(gid: int):
    """Alış faturasının satırlarını, önerilen ürün eşleşmeleriyle döndürür."""
    with db.islem() as con:
        g = con.execute("SELECT * FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
        if not g:
            hata("Fatura bulunamadı.", 404)
        satirlar = json.loads(g["satirlar_json"] or "[]")
        mevcut = {r["satir_ad"]: r["urun_id"] for r in con.execute(
            "SELECT satir_ad, urun_id FROM stok_hareketleri WHERE kaynak='alis' AND kaynak_id=?", (gid,))}
        for s in satirlar:
            s["urun_id"] = mevcut.get(s.get("ad")) or urun_bul(con, s.get("ad"), g["cari_id"])
        return {"satirlar": satirlar, "stoka_alindi": bool(mevcut),
                "irsaliyeli": bool(con.execute("SELECT 1 FROM irsaliyeler WHERE gelen_fatura_id=?", (gid,)).fetchone())}


@router.post("/api/gelen/{gid}/stoka-al")
def gelen_stoka_al(gid: int, v: dict):
    with db.islem() as con:
        g = con.execute("SELECT * FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
        if not g:
            hata("Fatura bulunamadı.", 404)
        ters = {"Adet": "C62", "Saat": "HUR", "Gün": "DAY", "Ay": "MON", "Kg": "KGM", "Litre": "LTR", "Metre": "MTR",
                "m²": "MTK", "Set": "SET", "Kutu": "BX"}
        satirlar = []
        for s, secim in zip(json.loads(g["satirlar_json"] or "[]"), v.get("urunler") or []):
            satirlar.append({**s, "birim": ters.get(s.get("birim"), s.get("birim") or "C62"), "urun_id": secim})
        satirlar = satirlari_bagla(con, satirlar, g["cari_id"])
        iade = g["tip"] == "IADE"
        kaynak_yaz(con, "alis", gid, g["tarih"], satirlar, +1, "GELEN_IADE" if iade else "ALIS")
        adet = con.execute("SELECT COUNT(*) FROM stok_hareketleri WHERE kaynak='alis' AND kaynak_id=?", (gid,)).fetchone()[0]
    return {"ok": True, "adet": adet}
