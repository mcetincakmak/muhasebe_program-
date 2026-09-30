"""İrsaliyeler."""
import json
import os
import re

from fastapi import APIRouter, HTTPException

from ..core import db
from ..core.ortak import hata
from ..servisler import stok
from ..servisler.eslestirme import cari_bul_veya_olustur, eslestir
from ..servisler.okuma import OkumaHatasi, belge_oku

router = APIRouter()


from .belgeler import _fotolari_kaydet

# ------------------------------------------------------------------ irsaliyeler
IRS_SQL = ("SELECT i.*, c.unvan AS cari_unvan, g.fatura_no AS fatura_no, g.tarih AS fatura_tarih, "
           "o.fatura_no AS oneri_fatura_no, o.tarih AS oneri_tarih, o.tutar AS oneri_tutar "
           "FROM irsaliyeler i LEFT JOIN cariler c ON c.id=i.cari_id "
           "LEFT JOIN gelen_faturalar g ON g.id=i.gelen_fatura_id LEFT JOIN gelen_faturalar o ON o.id=i.oneri_fatura_id")


def _irs(con, iid):
    r = con.execute(IRS_SQL + " WHERE i.id=?", (iid,)).fetchone()
    if not r:
        hata("İrsaliye bulunamadı.", 404)
    d = dict(r)
    d["satirlar"] = json.loads(d.pop("satirlar_json") or "[]")
    d["fotolar"] = json.loads(d.pop("fotolar_json") or "[]")
    d["okuma"] = json.loads(d.pop("okuma_json") or "{}")
    return d


def _irs_alanlar(con, v, iid=None):
    """Form verisini doğrular, cariyi bulur/oluşturur."""
    no = re.sub(r"\s", "", (v.get("irsaliye_no") or "")).upper()
    vkn = re.sub(r"\D", "", v.get("gonderen_vkn") or "")
    unvan = (v.get("gonderen_unvan") or "").strip()
    if not no:
        hata("İrsaliye numarasını girin.")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v.get("tarih") or ""):
        hata("İrsaliye tarihini girin.")
    if vkn and len(vkn) not in (10, 11):
        hata("Tedarikçi VKN 10, TCKN 11 haneli olmalı.")
    if not vkn and not unvan and not v.get("cari_id"):
        hata("Tedarikçiyi seçin veya ünvan/VKN girin.")
    cari_id = v.get("cari_id")
    if cari_id:
        c = con.execute("SELECT * FROM cariler WHERE id=?", (cari_id,)).fetchone()
        if not c:
            hata("Tedarikçi bulunamadı.")
        if c["tur"] == "musteri":
            con.execute("UPDATE cariler SET tur='ikisi' WHERE id=?", (cari_id,))
        vkn, unvan = vkn or c["vkn"] or "", c["unvan"]
    else:
        cari_id = cari_bul_veya_olustur(con, {"unvan": unvan, "vkn": vkn, "vergi_dairesi": v.get("vergi_dairesi"),
                                              "il": v.get("il")}, "tedarikci")
        c = con.execute("SELECT unvan, vkn FROM cariler WHERE id=?", (cari_id,)).fetchone()
        unvan, vkn = c["unvan"], vkn or c["vkn"] or ""
    ayni = con.execute("SELECT id FROM irsaliyeler WHERE irsaliye_no=? AND (cari_id=? OR (gonderen_vkn=? AND ?!='')) "
                       "AND id!=?", (no, cari_id, vkn, vkn, iid or 0)).fetchone()
    if ayni:
        hata(f"Bu irsaliye zaten kayıtlı (İrsaliyeler listesinde #{ayni['id']}). Aynı irsaliyeyi iki kez yüklemiş olabilirsiniz.")
    satirlar = [{"ad": s["ad"].strip(), "miktar": float(s.get("miktar") or 0), "birim": s.get("birim") or "C62",
                 "urun_id": s.get("urun_id")}
                for s in v.get("satirlar") or [] if (s.get("ad") or "").strip()]
    satirlar = stok.satirlari_bagla(con, satirlar, cari_id)
    return {"irsaliye_no": no, "tarih": v["tarih"], "gonderen_vkn": vkn, "gonderen_unvan": unvan, "cari_id": cari_id,
            "satirlar_json": json.dumps(satirlar, ensure_ascii=False), "notlar": v.get("notlar") or ""}


@router.get("/api/irsaliyeler")
def irsaliyeler(durum: str = ""):
    sql, p = IRS_SQL, []
    if durum:
        sql += " WHERE i.durum=?"
        p.append(durum)
    with db.islem() as con:
        liste = []
        for r in con.execute(sql + " ORDER BY i.tarih DESC, i.id DESC LIMIT 500", p):
            d = dict(r)
            d["foto"] = (json.loads(d["fotolar_json"] or "[]") or [None])[0]
            for k in ("satirlar_json", "fotolar_json", "okuma_json"):
                d.pop(k, None)
            liste.append(d)
        return liste


@router.post("/api/irsaliyeler/yukle")
def irsaliye_yukle(v: dict):
    """Fotoğrafları kaydeder ve okur. Temel alanlar okunduysa kaydı hazır eder, değilse kontrole bırakır."""
    fotolar = _fotolari_kaydet(v.get("fotolar"))
    if not fotolar:
        hata("En az bir fotoğraf yükleyin.")
    ayar = db.ayarlar_hepsi()
    okuma, okuma_hatasi = {}, ""
    try:
        okuma, _ = belge_oku([(mime, ham) for _, mime, ham in fotolar], ayar)
    except OkumaHatasi as e:
        okuma_hatasi = str(e)
    g = okuma.get("gonderen") or {}
    tam = bool(okuma.get("belge_no") and okuma.get("tarih") and (g.get("vkn") or g.get("unvan")))
    with db.islem() as con:
        alanlar = {"irsaliye_no": okuma.get("belge_no") or "", "tarih": okuma.get("tarih") or "",
                   "gonderen_vkn": g.get("vkn") or "", "gonderen_unvan": g.get("unvan") or "", "cari_id": None,
                   "satirlar_json": json.dumps(okuma.get("satirlar") or [], ensure_ascii=False), "notlar": ""}
        durum = "KONTROL"
        if tam and ayar.get("otomatik_kaydet", "1") == "1":
            try:
                alanlar = _irs_alanlar(con, {**alanlar, "satirlar": okuma.get("satirlar"),
                                             "vergi_dairesi": g.get("vergi_dairesi"), "il": g.get("il")})
                durum = "BEKLIYOR"
            except HTTPException as e:
                okuma_hatasi = e.detail
        okuma["_hata"] = okuma_hatasi
        cur = con.execute(
            "INSERT INTO irsaliyeler(irsaliye_no,tarih,gonderen_vkn,gonderen_unvan,cari_id,satirlar_json,notlar,"
            "fotolar_json,kaynak,okuma_json,durum) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (alanlar["irsaliye_no"], alanlar["tarih"], alanlar["gonderen_vkn"], alanlar["gonderen_unvan"],
             alanlar["cari_id"], alanlar["satirlar_json"], alanlar["notlar"],
             json.dumps([ad for ad, _, _ in fotolar]), "foto", json.dumps(okuma, ensure_ascii=False), durum))
        iid = cur.lastrowid
        stok.irsaliye_stok_yaz(con, iid)
    if durum == "BEKLIYOR":
        eslestir()
    with db.islem() as con:
        return _irs(con, iid)


@router.post("/api/irsaliyeler")
def irsaliye_ekle(v: dict):
    with db.islem() as con:
        a = _irs_alanlar(con, v)
        fotolar = [ad for ad, _, _ in _fotolari_kaydet(v.get("fotolar"))]
        cur = con.execute(
            f"INSERT INTO irsaliyeler({','.join(a)},fotolar_json,kaynak,durum) VALUES({','.join('?' * len(a))},?,?,?)",
            list(a.values()) + [json.dumps(fotolar), "manuel", "BEKLIYOR"])
        iid = cur.lastrowid
        stok.irsaliye_stok_yaz(con, iid)
    eslestir()
    with db.islem() as con:
        return _irs(con, iid)


@router.get("/api/irsaliyeler/{iid}")
def irsaliye(iid: int):
    with db.islem() as con:
        return _irs(con, iid)


@router.put("/api/irsaliyeler/{iid}")
def irsaliye_guncelle(iid: int, v: dict):
    with db.islem() as con:
        eski = _irs(con, iid)
        a = _irs_alanlar(con, v, iid)
        durum = eski["durum"] if eski["durum"] == "ESLESTI" else "BEKLIYOR"
        con.execute(f"UPDATE irsaliyeler SET {','.join(k + '=?' for k in a)}, durum=? WHERE id=?",
                    list(a.values()) + [durum, iid])
        stok.irsaliye_stok_yaz(con, iid)
    if durum == "BEKLIYOR":
        eslestir()
    with db.islem() as con:
        return _irs(con, iid)


@router.delete("/api/irsaliyeler/{iid}")
def irsaliye_sil(iid: int):
    with db.islem() as con:
        i = _irs(con, iid)
        for ad in i["fotolar"]:
            try:
                os.remove(os.path.join(db.belge_dizini(), ad))
            except OSError:
                pass
        con.execute("DELETE FROM irsaliyeler WHERE id=?", (iid,))
        stok.kaynak_sil(con, "irsaliye", iid)
    return {"ok": True}


@router.post("/api/irsaliyeler/{iid}/eslesme")
def irsaliye_eslesme(iid: int, v: dict):
    """islem: onayla | reddet | kaldir | bagla (gelen_id ile)"""
    islem_ = v.get("islem")
    with db.islem() as con:
        i = _irs(con, iid)
        if islem_ == "onayla" and i["oneri_fatura_id"]:
            con.execute("UPDATE irsaliyeler SET durum='ESLESTI', gelen_fatura_id=oneri_fatura_id, oneri_fatura_id=NULL, "
                        "eslesme_aciklama=COALESCE(eslesme_aciklama,'') || ' (onaylandı)' WHERE id=?", (iid,))
        elif islem_ == "reddet" and i["oneri_fatura_id"]:
            red = set(json.loads(con.execute("SELECT reddedilen_json FROM irsaliyeler WHERE id=?", (iid,)).fetchone()[0] or "[]"))
            red.add(i["oneri_fatura_id"])
            con.execute("UPDATE irsaliyeler SET durum='BEKLIYOR', oneri_fatura_id=NULL, eslesme_puani=NULL, "
                        "eslesme_aciklama=NULL, reddedilen_json=? WHERE id=?", (json.dumps(sorted(red)), iid))
        elif islem_ == "kaldir":
            red = set(json.loads(con.execute("SELECT reddedilen_json FROM irsaliyeler WHERE id=?", (iid,)).fetchone()[0] or "[]"))
            if i["gelen_fatura_id"]:
                red.add(i["gelen_fatura_id"])
            con.execute("UPDATE irsaliyeler SET durum='BEKLIYOR', gelen_fatura_id=NULL, eslesme_puani=NULL, "
                        "eslesme_aciklama=NULL, reddedilen_json=? WHERE id=?", (json.dumps(sorted(red)), iid))
        elif islem_ == "bagla":
            gid = v.get("gelen_id")
            if not con.execute("SELECT 1 FROM gelen_faturalar WHERE id=?", (gid,)).fetchone():
                hata("Fatura bulunamadı.")
            con.execute("UPDATE irsaliyeler SET durum='ESLESTI', gelen_fatura_id=?, oneri_fatura_id=NULL, "
                        "eslesme_puani=NULL, eslesme_aciklama='Elle eşleştirildi' WHERE id=?", (gid, iid))
        else:
            hata("Geçersiz işlem.")
    if islem_ in ("reddet", "kaldir"):
        eslestir()
    else:
        stok.irsaliye_fiyatlari()
    with db.islem() as con:
        return _irs(con, iid)


