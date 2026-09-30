"""Satış ve iade faturaları."""
import json
import re
import uuid as uuidlib
from datetime import datetime

from fastapi import APIRouter, Response

from .. import entegrator
from ..core import db
from ..core.ortak import GONDERIM_KILIDI, firma, hata
from ..entegrator import EntegratorHatasi
from ..servisler import stok
from ..servisler.vade import vade_belirle
from ..servisler.ubl import (BIRIMLER, PARA_BIRIMLERI, TEVKIFAT_KODLARI, fatura_xml, hesapla)

router = APIRouter()


# ------------------------------------------------------------------ faturalar
def _fatura_getir(con, fid):
    f = con.execute("SELECT * FROM faturalar WHERE id=?", (fid,)).fetchone()
    if not f:
        hata("Fatura bulunamadı.", 404)
    f = dict(f)
    f["satirlar"] = json.loads(f.pop("satirlar_json") or "[]")
    f["cari"] = json.loads(f.pop("cari_json") or "{}")
    f["iade_ref"] = json.loads(f.pop("iade_ref_json") or "[]")
    f["fatura_turu"] = f.get("fatura_turu") or "SATIS"
    f.pop("xml", None)
    return f


def _fatura_veri(v, con):
    cari = con.execute("SELECT * FROM cariler WHERE id=?", (v.get("cari_id"),)).fetchone()
    if not cari:
        hata("Lütfen bir müşteri seçin.")
    satirlar = [s for s in v.get("satirlar", []) if (s.get("ad") or "").strip()]
    if not satirlar:
        hata("Faturaya en az bir satır ekleyin.")
    if len(satirlar) > 500:
        hata("Bir faturada en fazla 500 satır olabilir.")
    for s in satirlar:
        s["ad"] = s["ad"].strip()[:300]
        try:
            miktar, fiyat = float(s.get("miktar") or 0), float(s.get("birim_fiyat") or 0)
            kdv, isk = float(s.get("kdv") if s.get("kdv") not in (None, "") else 20), float(s.get("iskonto") or 0)
        except (TypeError, ValueError):
            hata(f"'{s['ad']}' satırında miktar, fiyat, KDV ve iskonto rakam olmalı.")
        if miktar <= 0 or miktar > 1e9:
            hata(f"'{s['ad']}' satırında miktar sıfırdan büyük olmalı.")
        if fiyat < 0 or fiyat > 1e12:
            hata(f"'{s['ad']}' satırında fiyat geçersiz.")
        if kdv not in (0, 1, 8, 10, 18, 20):
            hata(f"'{s['ad']}' satırında geçersiz KDV oranı.")
        if not 0 <= isk <= 100:
            hata(f"'{s['ad']}' satırında iskonto 0 ile 100 arasında olmalı.")
        if s.get("birim") not in BIRIMLER:
            s["birim"] = "C62"
    satirlar = stok.satirlari_bagla(con, satirlar, None, yeni_olustur=False)
    h = hesapla(satirlar)
    tarih = v.get("tarih") or datetime.now().strftime("%Y-%m-%d")
    para = v.get("para_birimi") if v.get("para_birimi") in PARA_BIRIMLERI else "TRY"
    try:
        kur = 1.0 if para == "TRY" else float(str(v.get("kur") or "0").replace(",", "."))
    except ValueError:
        kur = 0
    if kur <= 0:
        hata(f"{para} faturası için döviz kurunu girin.")
    for s in satirlar:
        if s.get("tevkifat_kod") and str(s["tevkifat_kod"]) not in TEVKIFAT_KODLARI:
            hata(f"'{s['ad']}' satırında geçersiz tevkifat kodu.")
    fatura_turu = "IADE" if v.get("fatura_turu") == "IADE" else "SATIS"
    iade_ref = [r for r in (v.get("iade_ref") or []) if (r.get("no") or "").strip()]
    if fatura_turu == "IADE":
        if not iade_ref:
            hata("İade faturası için iade edilen faturanın numarasını ve tarihini girin.")
        for r in iade_ref:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", r.get("tarih") or ""):
                hata("İade edilen faturanın tarihini girin.")
    return {
        "cari_id": cari["id"], "cari_json": json.dumps(dict(cari), ensure_ascii=False),
        "satirlar_json": json.dumps(h["satirlar"], ensure_ascii=False),
        "tarih": tarih, "notlar": v.get("notlar") or "",
        "vade_tarihi": vade_belirle(con, cari["id"], tarih, (v.get("vade_tarihi") or "").strip()),
        "senaryo": v.get("senaryo") if v.get("senaryo") in ("TEMELFATURA", "TICARIFATURA") else "TEMELFATURA",
        "tip": "EFATURA" if cari["efatura_mukellefi"] else "EARSIV",
        "brut_toplam": h["brut_toplam"], "iskonto_toplam": h["iskonto_toplam"], "matrah": h["matrah"],
        "kdv_toplam": h["kdv_toplam"], "genel_toplam": h["genel_toplam"],
        "fatura_turu": fatura_turu, "para_birimi": para, "kur": kur, "tevkifat_toplam": h["tevkifat_toplam"],
        "iade_ref_json": json.dumps([{"no": r["no"].strip().upper(), "tarih": r["tarih"]} for r in iade_ref]
                                    if fatura_turu == "IADE" else [], ensure_ascii=False),
    }


@router.get("/api/faturalar")
def faturalar(q: str = "", durum: str = ""):
    sql = ("SELECT id, fatura_no, tip, tarih, durum, durum_aciklama, genel_toplam, para_birimi, fatura_turu, kur, "
           "json_extract(cari_json,'$.unvan') AS cari_unvan FROM faturalar WHERE 1=1")
    p = []
    if q:
        sql += " AND (fatura_no LIKE ? OR json_extract(cari_json,'$.unvan') LIKE ?)"
        p += [f"%{q}%", f"%{q}%"]
    if durum:
        sql += " AND durum=?"
        p.append(durum)
    with db.islem() as con:
        return [dict(r) for r in con.execute(sql + " ORDER BY tarih DESC, id DESC LIMIT 500", p)]


@router.get("/api/faturalar/{fid}")
def fatura(fid: int):
    with db.islem() as con:
        return _fatura_getir(con, fid)


@router.post("/api/faturalar")
def fatura_olustur(v: dict):
    with db.islem() as con:
        alanlar = _fatura_veri(v, con)
        alanlar["uuid"] = str(uuidlib.uuid4()).upper()
        cur = con.execute(f"INSERT INTO faturalar({','.join(alanlar)}) VALUES({','.join('?' * len(alanlar))})",
                          list(alanlar.values()))
        return _fatura_getir(con, cur.lastrowid)


@router.put("/api/faturalar/{fid}")
def fatura_guncelle(fid: int, v: dict):
    with db.islem() as con:
        if _fatura_getir(con, fid)["durum"] != "TASLAK":
            hata("Gönderilmiş fatura değiştirilemez.")
        alanlar = _fatura_veri(v, con)
        alanlar["guncelleme"] = datetime.now().isoformat(timespec="seconds")
        con.execute(f"UPDATE faturalar SET {','.join(k + '=?' for k in alanlar)} WHERE id=?",
                    list(alanlar.values()) + [fid])
        return _fatura_getir(con, fid)


@router.delete("/api/faturalar/{fid}")
def fatura_sil(fid: int):
    with db.islem() as con:
        if _fatura_getir(con, fid)["durum"] != "TASLAK":
            hata("Sadece taslak faturalar silinebilir.")
        con.execute("DELETE FROM faturalar WHERE id=?", (fid,))
    return {"ok": True}


@router.post("/api/faturalar/{fid}/gonder")
def fatura_gonder(fid: int):
    if not GONDERIM_KILIDI.acquire(timeout=120):
        hata("Başka bir fatura gönderiliyor, biraz sonra tekrar deneyin.", 409)
    try:
        return _fatura_gonder(fid)
    finally:
        GONDERIM_KILIDI.release()


def _fatura_gonder(fid: int):
    ayar = db.ayarlar_hepsi()
    fr = firma()
    eksik = [ad for ad, k in (("ünvan", "unvan"), ("VKN", "vkn"), ("vergi dairesi", "vergi_dairesi"), ("il", "il"))
             if not fr.get(k)]
    if eksik:
        hata("Önce Ayarlar'dan firma bilgilerinizi tamamlayın: " + ", ".join(eksik) + ".")
    istemci = entegrator.istemci(ayar)

    with db.islem() as con:
        f = _fatura_getir(con, fid)
        if f["durum"] not in ("TASLAK", "HATA"):
            hata("Bu fatura zaten gönderilmiş.")
        # Mükellef durumunu gönderim anında tekrar kontrol et
        cari = dict(con.execute("SELECT * FROM cariler WHERE id=?", (f["cari_id"],)).fetchone() or f["cari"])
    if cari.get("vkn"):
        mukellef, etiket = istemci.efatura_mukellefi_mi(cari["vkn"])
        cari["efatura_mukellefi"], cari["posta_kutusu"] = int(mukellef), etiket
        with db.islem() as con:
            con.execute("UPDATE cariler SET efatura_mukellefi=?, posta_kutusu=?, mukellef_sorgu=? WHERE id=?",
                        (int(mukellef), etiket, datetime.now().isoformat(timespec="minutes"), cari["id"]))
    else:
        cari["vkn"] = "11111111111"  # GİB kuralı: kimlik bilinmeyen nihai tüketici
    tip = "EFATURA" if cari.get("efatura_mukellefi") else "EARSIV"
    if f["fatura_no"] and f["tip"]:
        tip = f["tip"]  # numara daha önce bir seriden verildiyse (hatalı gönderimi tekrar deneme) türü değiştirme

    with db.islem() as con:
        yil = int(f["tarih"][:4])
        no = f["fatura_no"] or db.sonraki_numara(con, ayar.get("seri_efatura" if tip == "EFATURA" else "seri_earsiv", "EFT"), yil)
        saat = datetime.now().strftime("%H:%M:%S")
        xml = fatura_xml({**f, "fatura_no": no, "tip": tip, "saat": saat}, fr, cari)  # iade_ref, fatura_turu f içinde
        con.execute("UPDATE faturalar SET fatura_no=?, tip=?, saat=?, xml=?, cari_json=? WHERE id=?",
                    (no, tip, saat, xml, json.dumps(cari, ensure_ascii=False), fid))

    try:
        if tip == "EFATURA":
            sonuc = istemci.efatura_gonder(xml, no, cari.get("posta_kutusu"))
        else:
            sonuc = istemci.earsiv_gonder(xml, no, f["uuid"], cari.get("eposta"))
    except EntegratorHatasi as e:
        with db.islem() as con:
            con.execute("UPDATE faturalar SET durum='HATA', durum_aciklama=? WHERE id=?", (str(e), fid))
        raise

    with db.islem() as con:
        con.execute("UPDATE faturalar SET durum=?, durum_aciklama=?, entegrator_id=?, guncelleme=? WHERE id=?",
                    (sonuc["durum"], sonuc["aciklama"], sonuc["id"], datetime.now().isoformat(timespec="seconds"), fid))
        stok.kaynak_yaz(con, "fatura", fid, f["tarih"], f["satirlar"], -1,
                        "ALIS_IADE" if f["fatura_turu"] == "IADE" else "SATIS")
        return _fatura_getir(con, fid)


@router.put("/api/faturalar/{fid}/vade")
def fatura_vade(fid: int, v: dict):
    """Vade tarihini değiştirir (ör. müşteriyle yeni ödeme günü konuşuldu). Gönderilmiş XML değişmez;
    yalnızca vade takibi bu tarihi kullanır. Boş gönderilirse vade = fatura tarihi."""
    with db.islem() as con:
        f = _fatura_getir(con, fid)
        vade = (v.get("vade_tarihi") or "").strip()
        con.execute("UPDATE faturalar SET vade_tarihi=? WHERE id=?",
                    (vade_belirle(con, None, f["tarih"], vade) if vade else None, fid))
        return _fatura_getir(con, fid)


@router.post("/api/faturalar/{fid}/durum-sorgula")
def fatura_durum(fid: int):
    with db.islem() as con:
        f = _fatura_getir(con, fid)
    if f["tip"] != "EFATURA" or not f["entegrator_id"]:
        return f
    sonuc = entegrator.istemci(db.ayarlar_hepsi()).efatura_durum(f["entegrator_id"])
    with db.islem() as con:
        con.execute("UPDATE faturalar SET durum=?, durum_aciklama=? WHERE id=?", (sonuc["durum"], sonuc["aciklama"], fid))
        return _fatura_getir(con, fid)


@router.get("/api/faturalar/{fid}/xml")
def fatura_xml_indir(fid: int):
    with db.islem() as con:
        r = con.execute("SELECT fatura_no, xml FROM faturalar WHERE id=?", (fid,)).fetchone()
    if not r or not r["xml"]:
        hata("Bu faturanın XML'i henüz oluşturulmadı (fatura gönderilmemiş).", 404)
    return Response(r["xml"], media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{r["fatura_no"]}.xml"'})


