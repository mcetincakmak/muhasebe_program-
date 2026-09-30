"""Cari hesap: bakiye, ekstre, tahsilat/ödeme, kasa ve banka hesapları.

İşaret kuralı (cari açısından):
  borç   : Kestiğimiz satış/iade faturası, yaptığımız ödeme, borç açılış bakiyesi
  alacak : Gelen alış faturası, aldığımız tahsilat, alacak açılış bakiyesi
  bakiye = borç - alacak  ->  artı: cari bize borçlu  |  eksi: biz cariye borçluyuz
"""
import html
import re
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..core import db
from ..core.ortak import hata

router = APIRouter()

TURLER = {
    "TAHSILAT": "Tahsilat", "ODEME": "Ödeme", "DEVIR_BORC": "Açılış bakiyesi (cari borçlu)",
    "DEVIR_ALACAK": "Açılış bakiyesi (cari alacaklı)", "GELIR": "Diğer gelir", "MASRAF": "Masraf",
    "VIRMAN": "Hesaplar arası transfer",
}
ODEME_SEKILLERI = ["Nakit", "Havale/EFT", "Kredi kartı", "Çek", "Senet", "Diğer"]

CARI_KALEMLER = """
SELECT 'fatura' AS kaynak, f.id AS kaynak_id, f.cari_id, f.tarih,
       CASE WHEN f.fatura_turu='IADE' THEN 'İade faturası' ELSE 'Satış faturası' END AS islem,
       f.fatura_no AS belge_no, CASE WHEN f.para_birimi!='TRY' THEN f.para_birimi || ' ' || printf('%.2f', f.genel_toplam) || ' × ' || f.kur ELSE '' END AS aciklama,
       ROUND(f.genel_toplam*COALESCE(f.kur,1), 2) AS borc, 0 AS alacak, 1 AS oncelik
  FROM faturalar f WHERE f.durum IN ('GONDERILDI','ONAYLANDI') AND f.cari_id IS NOT NULL
UNION ALL
SELECT 'alis', g.id, g.cari_id, g.tarih,
       CASE WHEN g.tip='IADE' THEN 'Gelen iade faturası' ELSE 'Alış faturası' END,
       g.fatura_no, CASE WHEN COALESCE(g.para_birimi,'TRY')!='TRY' THEN g.para_birimi || ' ' || printf('%.2f', g.tutar) || ' × ' || g.kur ELSE '' END,
       0, ROUND(g.tutar*COALESCE(g.kur,1), 2), 1
  FROM gelen_faturalar g WHERE g.cari_id IS NOT NULL
UNION ALL
SELECT 'hareket', h.id, h.cari_id, h.tarih,
       CASE h.tur WHEN 'TAHSILAT' THEN 'Tahsilat' WHEN 'ODEME' THEN 'Ödeme' ELSE 'Açılış bakiyesi' END
         || CASE WHEN h.odeme_sekli IS NOT NULL AND h.odeme_sekli != '' THEN ' (' || h.odeme_sekli || ')' ELSE '' END,
       h.belge_no, h.aciklama,
       CASE WHEN h.tur IN ('ODEME','DEVIR_BORC') THEN h.tutar ELSE 0 END,
       CASE WHEN h.tur IN ('TAHSILAT','DEVIR_ALACAK') THEN h.tutar ELSE 0 END,
       CASE WHEN h.tur LIKE 'DEVIR%' THEN 0 ELSE 2 END
  FROM hareketler h WHERE h.cari_id IS NOT NULL AND h.tur IN ('TAHSILAT','ODEME','DEVIR_BORC','DEVIR_ALACAK')
"""

HESAP_KALEMLER = """
SELECT h.id, h.tarih, h.tur, h.cari_id, c.unvan AS cari_unvan, h.odeme_sekli, h.belge_no, h.aciklama,
       h.hesap_id, h.hedef_hesap_id,
       CASE WHEN (h.tur IN ('TAHSILAT','GELIR') AND h.hesap_id=:hid) OR (h.tur='VIRMAN' AND h.hedef_hesap_id=:hid)
            THEN h.tutar ELSE 0 END AS giris,
       CASE WHEN (h.tur IN ('ODEME','MASRAF','VIRMAN') AND h.hesap_id=:hid) THEN h.tutar ELSE 0 END AS cikis
  FROM hareketler h LEFT JOIN cariler c ON c.id=h.cari_id
 WHERE h.hesap_id=:hid OR h.hedef_hesap_id=:hid
"""


def _k(x):
    return round(float(x or 0) + 1e-9, 2)


def _tarih_mi(t):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", t or ""))


# ------------------------------------------------------------------ bakiyeler
def cari_bakiyeleri(con):
    return {r["cari_id"]: _k(r["b"]) for r in con.execute(
        f"SELECT cari_id, SUM(borc) - SUM(alacak) AS b FROM ({CARI_KALEMLER}) GROUP BY cari_id")}


def hesap_bakiyeleri(con):
    sonuc = {}
    for h in con.execute("SELECT * FROM hesaplar"):
        r = con.execute(f"SELECT COALESCE(SUM(giris),0) g, COALESCE(SUM(cikis),0) c FROM ({HESAP_KALEMLER})",
                        {"hid": h["id"]}).fetchone()
        sonuc[h["id"]] = _k(h["acilis_bakiye"] + r["g"] - r["c"])
    return sonuc


def ozet_bilgi():
    with db.islem() as con:
        b = cari_bakiyeleri(con)
        hb = hesap_bakiyeleri(con)
        aktif = {r["id"] for r in con.execute("SELECT id FROM hesaplar WHERE aktif=1")}
    return {"alacak_toplam": _k(sum(v for v in b.values() if v > 0)),
            "borc_toplam": _k(-sum(v for v in b.values() if v < 0)),
            "alacakli_cari": sum(1 for v in b.values() if v > 0.004),
            "borclu_oldugumuz": sum(1 for v in b.values() if v < -0.004),
            "kasa_banka": _k(sum(v for k, v in hb.items() if k in aktif))}


# ------------------------------------------------------------------ ekstre
def ekstre_verisi(cid, bas="", bit=""):
    with db.islem() as con:
        cari = con.execute("SELECT * FROM cariler WHERE id=?", (cid,)).fetchone()
        if not cari:
            hata("Cari bulunamadı.", 404)
        satirlar = [dict(r) for r in con.execute(
            f"SELECT * FROM ({CARI_KALEMLER}) WHERE cari_id=? ORDER BY tarih, oncelik, kaynak, kaynak_id", (cid,))]
    devir, liste, bakiye = 0.0, [], 0.0
    for r in satirlar:
        if bas and r["tarih"] < bas:
            devir += r["borc"] - r["alacak"]
            continue
        if bit and r["tarih"] > bit:
            continue
        liste.append(r)
    bakiye = devir
    for r in liste:
        bakiye += r["borc"] - r["alacak"]
        r["bakiye"] = _k(bakiye)
    return {
        "cari": dict(cari), "bas": bas, "bit": bit, "devir": _k(devir), "satirlar": liste,
        "toplam_borc": _k(sum(r["borc"] for r in liste)), "toplam_alacak": _k(sum(r["alacak"] for r in liste)),
        "bakiye": _k(bakiye),
    }


@router.get("/api/cariler/{cid}/ekstre")
def ekstre(cid: int, bas: str = "", bit: str = ""):
    e = ekstre_verisi(cid, bas if _tarih_mi(bas) else "", bit if _tarih_mi(bit) else "")
    with db.islem() as con:
        e["genel_bakiye"] = cari_bakiyeleri(con).get(cid, 0)
        e["faturalar"] = [dict(r) for r in con.execute(
            "SELECT id, fatura_no, tarih, ROUND(genel_toplam*COALESCE(kur,1),2) AS tutar, 'satis' AS yon FROM faturalar "
            "WHERE cari_id=? AND durum IN ('GONDERILDI','ONAYLANDI') "
            "UNION ALL SELECT id, fatura_no, tarih, ROUND(tutar*COALESCE(kur,1),2), 'alis' FROM gelen_faturalar WHERE cari_id=? "
            "ORDER BY tarih DESC LIMIT 50", (cid, cid))]
    return e


def _para(x):
    s = f"{float(x or 0):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _tr(t):
    return ".".join(reversed(t.split("-"))) if t else ""


@router.get("/goruntule/ekstre/{cid}")
def ekstre_yazdir(cid: int, bas: str = "", bit: str = ""):
    e = ekstre_verisi(cid, bas if _tarih_mi(bas) else "", bit if _tarih_mi(bit) else "")
    a = db.ayarlar_hepsi()
    esc = lambda x: html.escape(str(x or ""))
    c = e["cari"]
    donem = f"{_tr(e['bas']) or 'Başlangıç'} – {_tr(e['bit']) or _tr(datetime.now().strftime('%Y-%m-%d'))}"
    satirlar = ""
    if e["bas"]:
        satirlar += f"<tr><td>{_tr(e['bas'])}</td><td colspan='2'>Önceki dönemden devir</td><td></td><td></td><td class='s'>{_para(e['devir'])}</td></tr>"
    for r in e["satirlar"]:
        satirlar += (f"<tr><td>{_tr(r['tarih'])}</td><td>{esc(r['islem'])}</td><td>{esc(r['belge_no'])} {esc(r['aciklama'])}</td>"
                     f"<td class='s'>{_para(r['borc']) if r['borc'] else ''}</td><td class='s'>{_para(r['alacak']) if r['alacak'] else ''}</td>"
                     f"<td class='s'>{_para(abs(r['bakiye']))} {'B' if r['bakiye'] > 0 else 'A' if r['bakiye'] < 0 else ''}</td></tr>")
    b = e["bakiye"]
    durum = (f"{esc(c['unvan'])} firmasının {_tr(e['bit']) or 'bugün'} itibarıyla <strong>{_para(b)} TL borç</strong> bakiyesi vardır."
             if b > 0 else f"{esc(c['unvan'])} firmasının <strong>{_para(-b)} TL alacak</strong> bakiyesi vardır." if b < 0
             else "Hesap kapalıdır, bakiye yoktur.")
    return HTMLResponse(f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Hesap ekstresi – {esc(c['unvan'])}</title>
<style>
body{{font:13px/1.5 system-ui,sans-serif;color:#1d2521;max-width:900px;margin:24px auto;padding:0 16px}}
header{{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap;border-bottom:2px solid #1d2521;padding-bottom:10px}}
h1{{font-size:20px;margin:0}} table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:5px 6px;border-bottom:1px solid #d6ddd9;text-align:left;vertical-align:top}} th{{font-weight:600;color:#5c6862}}
.s{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}} tfoot td{{font-weight:700;border-top:2px solid #1d2521}}
.kutu{{margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:20px}} .soluk{{color:#5c6862}}
.imza{{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:40px}} .imza div{{border-top:1px solid #999;padding-top:6px}}
@media print{{.yazdir{{display:none}}}} @media (max-width:600px){{.kutu,.imza{{grid-template-columns:1fr}}}}
</style></head><body>
<p class="yazdir"><button onclick="print()">Yazdır / PDF kaydet</button></p>
<header><div><h1>Cari hesap ekstresi</h1><div class="soluk">Dönem: {donem}</div></div>
<div><strong>{esc(a.get('firma_unvan'))}</strong><br>VKN: {esc(a.get('firma_vkn'))}</div></header>
<div class="kutu"><div><div class="soluk">Cari</div><strong>{esc(c['unvan'])}</strong><br>{'VKN/TCKN: ' + esc(c['vkn']) if c['vkn'] else ''}
{'<br>V.D.: ' + esc(c['vergi_dairesi']) if c['vergi_dairesi'] else ''}</div>
<div><div class="soluk">Düzenleme tarihi</div>{datetime.now():%d.%m.%Y}</div></div>
<table><thead><tr><th>Tarih</th><th>İşlem</th><th>Belge / açıklama</th><th class="s">Borç</th><th class="s">Alacak</th><th class="s">Bakiye</th></tr></thead>
<tbody>{satirlar or '<tr><td colspan="6" class="soluk">Bu dönemde hareket yok.</td></tr>'}</tbody>
<tfoot><tr><td colspan="3">Toplam</td><td class="s">{_para(e['toplam_borc'])}</td><td class="s">{_para(e['toplam_alacak'])}</td>
<td class="s">{_para(abs(b))} {'B' if b > 0 else 'A' if b < 0 else ''}</td></tr></tfoot></table>
<p>{durum} B: borç, A: alacak bakiyesi.</p>
<p class="soluk">Mutabık olduğunuzu veya varsa farklılıkları bildirmenizi rica ederiz.</p>
<div class="imza"><div>{esc(a.get('firma_unvan'))}</div><div>{esc(c['unvan'])}</div></div>
</body></html>""")


# ------------------------------------------------------------------ hareketler (tahsilat, ödeme, devir, masraf, virman)
@router.get("/api/hareketler")
def hareketler(cari_id: int = 0, hesap_id: int = 0, limit: int = 200):
    sql = ("SELECT h.*, c.unvan AS cari_unvan, k.ad AS hesap_ad, t.ad AS hedef_hesap_ad FROM hareketler h "
           "LEFT JOIN cariler c ON c.id=h.cari_id LEFT JOIN hesaplar k ON k.id=h.hesap_id "
           "LEFT JOIN hesaplar t ON t.id=h.hedef_hesap_id WHERE 1=1")
    p = []
    if cari_id:
        sql += " AND h.cari_id=?"
        p.append(cari_id)
    if hesap_id:
        sql += " AND (h.hesap_id=? OR h.hedef_hesap_id=?)"
        p += [hesap_id, hesap_id]
    with db.islem() as con:
        return [dict(r) for r in con.execute(sql + " ORDER BY h.tarih DESC, h.id DESC LIMIT ?", p + [min(limit, 1000)])]


@router.post("/api/hareketler")
def hareket_ekle(v: dict):
    tur = v.get("tur")
    if tur not in TURLER:
        hata("Geçersiz işlem türü.")
    try:
        tutar = _k(str(v.get("tutar") or "0").replace(",", "."))
    except ValueError:
        hata("Tutarı rakamla girin.")
    if tutar <= 0:
        hata("Tutar sıfırdan büyük olmalı.")
    if not _tarih_mi(v.get("tarih")):
        hata("Tarihi girin.")
    cari_id = v.get("cari_id") or None
    hesap_id = v.get("hesap_id") or None
    hedef = v.get("hedef_hesap_id") or None
    with db.islem() as con:
        if tur in ("TAHSILAT", "ODEME", "DEVIR_BORC", "DEVIR_ALACAK"):
            if not cari_id or not con.execute("SELECT 1 FROM cariler WHERE id=?", (cari_id,)).fetchone():
                hata("Cariyi seçin.")
        else:
            cari_id = None
        if tur in ("DEVIR_BORC", "DEVIR_ALACAK"):
            hesap_id = hedef = None
        else:
            if not hesap_id or not con.execute("SELECT 1 FROM hesaplar WHERE id=?", (hesap_id,)).fetchone():
                hata("Kasa veya banka hesabını seçin.")
        if tur == "VIRMAN":
            if not hedef or int(hedef) == int(hesap_id) or not con.execute("SELECT 1 FROM hesaplar WHERE id=?", (hedef,)).fetchone():
                hata("Transfer için farklı bir hedef hesap seçin.")
        else:
            hedef = None
        if tur in ("GELIR", "MASRAF") and not (v.get("aciklama") or "").strip():
            hata("Açıklama girin (ör. kira, elektrik, banka masrafı).")
        fatura_id = gelen_id = None
        if v.get("fatura_ref"):  # "satis:12" veya "alis:5"
            yon, _, fid = str(v["fatura_ref"]).partition(":")
            tablo = "faturalar" if yon == "satis" else "gelen_faturalar"
            if not con.execute(f"SELECT 1 FROM {tablo} WHERE id=? AND cari_id=?", (fid, cari_id)).fetchone():
                hata("Seçilen fatura bu cariye ait değil.")
            fatura_id, gelen_id = (int(fid), None) if yon == "satis" else (None, int(fid))
        cur = con.execute(
            "INSERT INTO hareketler(tarih,tur,cari_id,hesap_id,hedef_hesap_id,tutar,odeme_sekli,belge_no,aciklama,"
            "fatura_id,gelen_fatura_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (v["tarih"], tur, cari_id, hesap_id, hedef, tutar,
             v.get("odeme_sekli") if v.get("odeme_sekli") in ODEME_SEKILLERI else None,
             (v.get("belge_no") or "").strip(), (v.get("aciklama") or "").strip(), fatura_id, gelen_id))
        return dict(con.execute("SELECT * FROM hareketler WHERE id=?", (cur.lastrowid,)).fetchone())


@router.delete("/api/hareketler/{hid}")
def hareket_sil(hid: int):
    with db.islem() as con:
        if not con.execute("SELECT 1 FROM hareketler WHERE id=?", (hid,)).fetchone():
            hata("Kayıt bulunamadı.", 404)
        con.execute("DELETE FROM hareketler WHERE id=?", (hid,))
    return {"ok": True}


# ------------------------------------------------------------------ kasa ve banka hesapları
@router.get("/api/hesaplar")
def hesaplar(hepsi: int = 0):
    with db.islem() as con:
        b = hesap_bakiyeleri(con)
        rows = con.execute("SELECT * FROM hesaplar" + ("" if hepsi else " WHERE aktif=1") + " ORDER BY tur DESC, ad")
        return [{**dict(r), "bakiye": b.get(r["id"], 0)} for r in rows]


def _hesap_alan(v):
    if not (v.get("ad") or "").strip():
        hata("Hesap adını girin (ör. Ziraat Bankası, Nakit kasa).")
    try:
        acilis = _k(str(v.get("acilis_bakiye") or "0").replace(",", "."))
    except ValueError:
        hata("Açılış bakiyesini rakamla girin.")
    return [v["ad"].strip(), "BANKA" if v.get("tur") == "BANKA" else "KASA",
            re.sub(r"\s", "", (v.get("iban") or "")).upper(), acilis]


@router.post("/api/hesaplar")
def hesap_ekle(v: dict):
    with db.islem() as con:
        cur = con.execute("INSERT INTO hesaplar(ad,tur,iban,acilis_bakiye) VALUES(?,?,?,?)", _hesap_alan(v))
        return dict(con.execute("SELECT * FROM hesaplar WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/api/hesaplar/{hid}")
def hesap_guncelle(hid: int, v: dict):
    with db.islem() as con:
        con.execute("UPDATE hesaplar SET ad=?, tur=?, iban=?, acilis_bakiye=? WHERE id=?", _hesap_alan(v) + [hid])
        return dict(con.execute("SELECT * FROM hesaplar WHERE id=?", (hid,)).fetchone())


@router.delete("/api/hesaplar/{hid}")
def hesap_kapat(hid: int):
    with db.islem() as con:
        if abs(hesap_bakiyeleri(con).get(hid, 0)) > 0.004:
            hata("Bakiyesi olan hesap kapatılamaz. Önce bakiyeyi başka hesaba aktarın.")
        con.execute("UPDATE hesaplar SET aktif=0 WHERE id=?", (hid,))
    return {"ok": True}


@router.get("/api/hesaplar/{hid}/hareketler")
def hesap_hareketleri(hid: int):
    with db.islem() as con:
        h = con.execute("SELECT * FROM hesaplar WHERE id=?", (hid,)).fetchone()
        if not h:
            hata("Hesap bulunamadı.", 404)
        rows = [dict(r) for r in con.execute(HESAP_KALEMLER + " ORDER BY h.tarih, h.id", {"hid": hid})]
    bakiye = h["acilis_bakiye"]
    for r in rows:
        bakiye += r["giris"] - r["cikis"]
        r["bakiye"] = _k(bakiye)
        r["tur_ad"] = TURLER.get(r["tur"], r["tur"])
    rows.reverse()
    return {"hesap": dict(h), "bakiye": _k(bakiye), "hareketler": rows}


@router.get("/api/cari-bakiyeleri")
def bakiyeler():
    with db.islem() as con:
        return cari_bakiyeleri(con)
