"""Özet ekranı verisi."""
from datetime import datetime

from fastapi import APIRouter

from ..core import db
from ..core.ortak import firma
from ..servisler import stok
from .cari_hesap import ozet_bilgi

from .faturalar import faturalar
from .vade import vade_ozeti

router = APIRouter()


def aktif_mod():
    """deneme | test | canli"""
    if (db.ayar_al("entegrator") or "deneme") == "deneme":
        return "deneme"
    return db.ayar_al("ent_ortam") or "test"


# ------------------------------------------------------------------ özet
@router.get("/api/ozet")
def ozet():
    ay = datetime.now().strftime("%Y-%m")
    with db.islem() as con:
        r = con.execute(
            "SELECT COUNT(*) adet, COALESCE(SUM(genel_toplam),0) toplam FROM faturalar "
            "WHERE durum IN ('GONDERILDI','ONAYLANDI') AND COALESCE(fatura_turu,'SATIS')='SATIS' "
            "AND substr(tarih,1,7)=?", (ay,)).fetchone()
        g = con.execute("SELECT COUNT(*) adet, COALESCE(SUM(tutar),0) toplam FROM gelen_faturalar "
                        "WHERE substr(tarih,1,7)=? AND COALESCE(tip,'SATIS')!='IADE'", (ay,)).fetchone()
        taslak = con.execute("SELECT COUNT(*) FROM faturalar WHERE durum='TASLAK'").fetchone()[0]
        hatali = con.execute("SELECT COUNT(*) FROM faturalar WHERE durum='HATA'").fetchone()[0]
        irs = {r["durum"]: r["n"] for r in con.execute("SELECT durum, COUNT(*) n FROM irsaliyeler GROUP BY durum")}
    return {"ay": ay, "kesilen_adet": r["adet"], "kesilen_toplam": r["toplam"],
            "gelen_adet": g["adet"], "gelen_toplam": g["toplam"], "taslak": taslak, "hatali": hatali,
            "mod": aktif_mod(), "firma_tamam": bool(firma()["vkn"]),
            "son": faturalar()[:5], "irsaliye": irs, "son_tarama": db.ayar_al("son_tarama", ""), **ozet_bilgi(),
            "kritik_stok": stok.kritik_sayisi(), "vade": vade_ozeti()}


