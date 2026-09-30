"""Vade takibi: açık (ödenmemiş) alacak ve borç kalemleri, gecikme günleri ve yaşlandırma.

Tahsilat ve ödemeler faturalara tek tek bağlanmaz; her carinin hesabında en eski vadeli kalem önce
kapanır (FIFO). Böylece bir carinin açık kalemlerinin toplamı her zaman cari bakiyesine eşittir:
bakiye artıysa en yeni vadeli borç kalemleri (satış faturaları), eksiyse en yeni vadeli alacak kalemleri
(alış faturaları) bakiyeyi oluşturacak kadarıyla açık kalır.
"""
from datetime import date

from fastapi import APIRouter

from ..core import db
from .cari_hesap import CARI_KALEMLER, _k

router = APIRouter()

GRUPLAR = [("gelmedi", "Vadesi gelmedi"), ("1-30", "1-30 gün"), ("31-60", "31-60 gün"), ("61-90", "61-90 gün"),
           ("90+", "90 günden fazla")]


def _grup(gecikme):
    if gecikme <= 0:
        return "gelmedi"
    if gecikme <= 30:
        return "1-30"
    if gecikme <= 60:
        return "31-60"
    if gecikme <= 90:
        return "61-90"
    return "90+"


def acik_kalemler(con, cari_id=None, bugun=None):
    """(alacaklar, borclar) listeleri. alacak: carinin bize borcu, borc: bizim cariye borcumuz."""
    bugun = bugun or date.today()
    sql = f"SELECT k.*, c.unvan AS cari_unvan FROM ({CARI_KALEMLER}) k JOIN cariler c ON c.id=k.cari_id"
    p = []
    if cari_id:
        sql += " WHERE k.cari_id=?"
        p.append(cari_id)
    carilere = {}
    for r in con.execute(sql, p):
        carilere.setdefault(r["cari_id"], []).append(dict(r))
    alacaklar, borclar = [], []
    for kalemler in carilere.values():
        bakiye = _k(sum(r["borc"] - r["alacak"] for r in kalemler))
        if abs(bakiye) < 0.005:
            continue
        yon, hedef, alan = ("alacak", alacaklar, "borc") if bakiye > 0 else ("borc", borclar, "alacak")
        kalan = abs(bakiye)
        # En yeni vadeden geriye doğru: eskiler ödemelerle kapanmış sayılır
        for r in sorted((r for r in kalemler if r[alan] > 0), key=lambda r: (r["vade"], r["tarih"], r["kaynak_id"]),
                        reverse=True):
            if kalan < 0.005:
                break
            acik = _k(min(r[alan], kalan))
            kalan = _k(kalan - acik)
            try:
                gecikme = (bugun - date.fromisoformat(r["vade"])).days
            except (TypeError, ValueError):
                gecikme = 0
            hedef.append({"yon": yon, "cari_id": r["cari_id"], "cari_unvan": r["cari_unvan"], "kaynak": r["kaynak"],
                          "kaynak_id": r["kaynak_id"], "islem": r["islem"], "belge_no": r["belge_no"],
                          "tarih": r["tarih"], "vade": r["vade"], "tutar": r[alan], "acik": acik,
                          "gecikme": gecikme, "grup": _grup(gecikme)})
    for liste in (alacaklar, borclar):
        liste.sort(key=lambda x: (x["vade"] or "", x["cari_unvan"]))
    return alacaklar, borclar


def _ozet(liste):
    gruplar = {k: 0.0 for k, _ in GRUPLAR}
    for x in liste:
        gruplar[x["grup"]] += x["acik"]
    gecen = [x for x in liste if x["gecikme"] > 0]
    return {"toplam": _k(sum(x["acik"] for x in liste)), "vadesi_gecen": _k(sum(x["acik"] for x in gecen)),
            "vadesi_gecen_adet": len(gecen), "gruplar": {k: _k(v) for k, v in gruplar.items()}}


def vade_ozeti():
    with db.islem() as con:
        alacaklar, borclar = acik_kalemler(con)
    return {"alacak": _ozet(alacaklar), "borc": _ozet(borclar)}


@router.get("/api/vade")
def vade_listesi(cari_id: int = 0):
    with db.islem() as con:
        alacaklar, borclar = acik_kalemler(con, cari_id or None)
    return {"bugun": date.today().isoformat(), "gruplar": dict(GRUPLAR),
            "alacaklar": alacaklar, "borclar": borclar, "ozet": {"alacak": _ozet(alacaklar), "borc": _ozet(borclar)}}
