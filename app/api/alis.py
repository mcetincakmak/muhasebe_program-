"""Alış faturaları (gelen e-faturalar ve elle girilenler), iade taslağı."""
import json
import re
import uuid as uuidlib

from fastapi import APIRouter, Response

from ..core import db
from ..core.ortak import hata
from ..servisler import stok
from ..servisler.eslestirme import cari_bul_veya_olustur, eslestir
from ..servisler.okuma import OkumaHatasi, belge_oku
from ..servisler.ubl import (BIRIMLER, hesapla, xml_satirlar)

router = APIRouter()


from ..servisler.tarama import tarama_yap
from .belgeler import _fotolari_kaydet
from .faturalar import fatura_olustur

# ------------------------------------------------------------------ gelen faturalar
@router.get("/api/gelen")
def gelen():
    with db.islem() as con:
        return [dict(r) for r in con.execute(
            "SELECT g.id, g.uuid, g.fatura_no, g.gonderen_unvan, g.gonderen_vkn, g.tarih, g.tutar, g.para_birimi, "
            "g.alinma, g.kaynak, g.tip, g.irsaliye_nolar, "
            "(SELECT COUNT(*) FROM irsaliyeler i WHERE i.gelen_fatura_id=g.id) AS irsaliye_sayisi "
            "FROM gelen_faturalar g ORDER BY g.tarih DESC, g.id DESC")]


@router.post("/api/gelen/yenile")
def gelen_yenile():
    sonuc = tarama_yap()
    sonuc["liste"] = gelen()
    return sonuc


@router.get("/api/gelen/{gid}/xml")
def gelen_xml(gid: int):
    with db.islem() as con:
        r = con.execute("SELECT fatura_no, xml FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
    if not r or not r["xml"]:
        hata("Bu faturanın XML'i yok (elle girilmiş fatura).", 404)
    return Response(r["xml"], media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{r["fatura_no"]}.xml"'})



# ------------------------------------------------------------------ alış faturaları (gelen) detay / elle giriş / iade
@router.get("/api/gelen/{gid}")
def gelen_detay(gid: int):
    with db.islem() as con:
        r = con.execute("SELECT * FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
        if not r:
            hata("Fatura bulunamadı.", 404)
        d = dict(r)
        d.pop("xml", None)
        d["xml_var"] = bool(r["xml"])
        d["satirlar"] = json.loads(d.pop("satirlar_json") or "[]") or (xml_satirlar(r["xml"]) if r["xml"] else [])
        d["fotolar"] = json.loads(d.pop("fotolar_json") or "[]")
        d["irsaliye_nolar"] = json.loads(d.get("irsaliye_nolar") or "[]")
        d["irsaliyeler"] = [dict(x) for x in con.execute(
            "SELECT id, irsaliye_no, tarih, eslesme_aciklama FROM irsaliyeler WHERE gelen_fatura_id=? ORDER BY tarih", (gid,))]
        d["iadeler"] = [dict(x) for x in con.execute(
            "SELECT id, fatura_no, tarih, durum, genel_toplam FROM faturalar WHERE fatura_turu='IADE' "
            "AND iade_ref_json LIKE ?", (f'%"{r["fatura_no"]}"%',))]
        return d


@router.post("/api/gelen/oku")
def gelen_foto_oku(v: dict):
    """Kağıt alış faturasının fotoğrafını kaydedip okur; formu doldurmak için sonucu döndürür."""
    fotolar = _fotolari_kaydet(v.get("fotolar"))
    try:
        okuma, _ = belge_oku([(mime, ham) for _, mime, ham in fotolar], db.ayarlar_hepsi())
    except OkumaHatasi as e:
        okuma = {"_hata": str(e)}
    return {"fotolar": [ad for ad, _, _ in fotolar], "okuma": okuma}


@router.post("/api/gelen")
def gelen_elle(v: dict):
    no = re.sub(r"\s", "", v.get("fatura_no") or "").upper()
    if not no:
        hata("Fatura numarasını girin.")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v.get("tarih") or ""):
        hata("Fatura tarihini girin.")
    satirlar = [s for s in v.get("satirlar") or [] if (s.get("ad") or "").strip()]
    h = hesapla(satirlar) if satirlar else None
    tutar = h["genel_toplam"] if h else float(v.get("tutar") or 0)
    if tutar <= 0:
        hata("Fatura satırlarını veya toplam tutarı girin.")
    with db.islem() as con:
        cari_id = v.get("cari_id") or cari_bul_veya_olustur(
            con, {"unvan": v.get("gonderen_unvan"), "vkn": v.get("gonderen_vkn")}, "tedarikci")
        if not cari_id:
            hata("Tedarikçiyi seçin veya ünvan/VKN girin.")
        c = con.execute("SELECT * FROM cariler WHERE id=?", (cari_id,)).fetchone()
        if c["tur"] == "musteri":
            con.execute("UPDATE cariler SET tur='ikisi' WHERE id=?", (cari_id,))
        irs_nolar = sorted({re.sub(r"\s", "", x).upper() for x in (v.get("irsaliye_nolar") or "").split(",") if x.strip()})
        cur = con.execute(
            "INSERT INTO gelen_faturalar(uuid,fatura_no,gonderen_unvan,gonderen_vkn,tarih,tutar,para_birimi,cari_id,"
            "satirlar_json,irsaliye_nolar,kaynak,matrah,kdv_toplam,fotolar_json,notlar,tip) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("MANUEL-" + uuidlib.uuid4().hex, no, c["unvan"], c["vkn"], v["tarih"], tutar, "TRY", cari_id,
             json.dumps([{"ad": s["ad"], "miktar": s.get("miktar"), "birim": BIRIMLER.get(s.get("birim"), s.get("birim")),
                          "birim_fiyat": s.get("birim_fiyat"), "kdv": s.get("kdv"), "tutar": s.get("matrah")}
                         for s in (h["satirlar"] if h else [])], ensure_ascii=False),
             json.dumps(irs_nolar), "manuel", h["matrah"] if h else None, h["kdv_toplam"] if h else None,
             json.dumps([x for x in v.get("fotolar") or [] if re.match(r"^[\w.-]+$", str(x))]),
             v.get("notlar") or "", "SATIS"))
        gid = cur.lastrowid
    eslestir()
    return gelen_detay(gid)


@router.delete("/api/gelen/{gid}")
def gelen_sil(gid: int):
    with db.islem() as con:
        r = con.execute("SELECT kaynak FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
        if not r:
            hata("Fatura bulunamadı.", 404)
        if r["kaynak"] != "manuel":
            hata("e-Faturalar silinemez; sadece elle girilen faturalar silinebilir.")
        con.execute("UPDATE irsaliyeler SET durum='BEKLIYOR', gelen_fatura_id=NULL WHERE gelen_fatura_id=?", (gid,))
        con.execute("UPDATE irsaliyeler SET durum='BEKLIYOR', oneri_fatura_id=NULL WHERE oneri_fatura_id=?", (gid,))
        con.execute("DELETE FROM gelen_faturalar WHERE id=?", (gid,))
        stok.kaynak_sil(con, "alis", gid)
    return {"ok": True}


@router.post("/api/gelen/{gid}/iade-taslak")
def iade_taslagi(gid: int):
    """Alış faturasından, tedarikçiye kesilecek iade faturası taslağı oluşturur."""
    g = gelen_detay(gid)
    if not g["cari_id"]:
        hata("Bu faturanın tedarikçisi tanımlı değil.")
    ters = {v: k for k, v in BIRIMLER.items()}
    satirlar = []
    for s in g["satirlar"]:
        try:
            fiyat = float(s.get("birim_fiyat") or 0)
        except ValueError:
            fiyat = 0
        satirlar.append({"ad": s.get("ad"), "miktar": float(s.get("miktar") or 1),
                         "birim": s.get("birim") if s.get("birim") in BIRIMLER else ters.get(s.get("birim"), "C62"),
                         "birim_fiyat": fiyat, "kdv": float(s.get("kdv") or 20), "iskonto": 0})
    if not satirlar:
        satirlar = [{"ad": "İade", "miktar": 1, "birim": "C62", "birim_fiyat": g["matrah"] or 0, "kdv": 20}]
    return fatura_olustur({"cari_id": g["cari_id"], "satirlar": satirlar, "fatura_turu": "IADE",
                           "iade_ref": [{"no": g["fatura_no"], "tarih": g["tarih"]}],
                           "notlar": f"{g['fatura_no']} numaralı faturaya ait iade."})


