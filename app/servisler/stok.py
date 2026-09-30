"""Stok takibi.

Stok hareketleri kaynaklardan otomatik oluşur:
  + İrsaliye (onaylanmış)            -> giriş
  + Alış faturası "Stoka al"         -> giriş (irsaliyesi olmayan alışlar için)
  - Satış faturası (gönderilince)    -> çıkış
  - İade faturası (tedarikçiye)      -> çıkış
  ± Açılış stoku, sayım düzeltmesi   -> elle
Faturadaki/irsaliyedeki satır ürüne; listeden seçilerek, stok koduyla, adıyla veya o tedarikçi için
daha önce yapılan eşleştirmeyle bağlanır.
"""
import json
import re

from ..core import db

TR = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUcgiiosu")
TUR_AD = {"ACILIS": "Açılış stoku", "SAYIM": "Sayım düzeltmesi", "IRSALIYE": "İrsaliye girişi",
          "ALIS": "Alış faturası girişi", "SATIS": "Satış", "ALIS_IADE": "Tedarikçiye iade", "GELEN_IADE": "Müşteri iadesi"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").translate(TR).lower())


def _k(x, n=4):
    return round(float(x or 0) + 1e-12, n)


# ------------------------------------------------------------------ eşleştirme
def urun_bul(con, ad, cari_id=None):
    anahtar = norm(ad)
    if not anahtar:
        return None
    if cari_id:
        r = con.execute("SELECT u.id FROM urun_eslesme e JOIN urunler u ON u.id=e.urun_id "
                        "WHERE e.cari_id=? AND e.anahtar=? AND u.aktif=1", (cari_id, anahtar)).fetchone()
        if r:
            return r["id"]
    urunler = con.execute("SELECT id, ad, kod FROM urunler WHERE aktif=1").fetchall()
    for u in urunler:  # stok kodu satırda ayrı bir kelime olarak geçiyorsa
        if u["kod"] and re.search(rf"(?<![A-Za-z0-9]){re.escape(u['kod'].strip())}(?![A-Za-z0-9])", ad or "", re.I):
            return u["id"]
    for u in urunler:
        if norm(u["ad"]) == anahtar:
            return u["id"]
    return None


def eslesme_ogren(con, cari_id, ad, urun_id):
    if cari_id and urun_id and norm(ad):
        con.execute("INSERT INTO urun_eslesme(cari_id, anahtar, urun_id) VALUES(?,?,?) "
                    "ON CONFLICT(cari_id, anahtar) DO UPDATE SET urun_id=excluded.urun_id", (cari_id, norm(ad), urun_id))


def satirlari_bagla(con, satirlar, cari_id=None, yeni_olustur=True):
    """Satırlardaki urun_id'yi doldurur. urun_id: sayı -> seçilmiş (öğrenilir), 'yeni' -> ürün açılır,
    0/'' -> stoka girmesin, yoksa otomatik bulunur."""
    sonuc = []
    for s in satirlar:
        s = dict(s)
        uid = s.get("urun_id")
        if uid == "yeni" and yeni_olustur:
            cur = con.execute("INSERT INTO urunler(ad, birim, fiyat, kdv, alis_fiyat, stok_takibi) VALUES(?,?,?,?,?,1)",
                              (s.get("ad", "").strip(), s.get("birim") or "C62", 0, float(s.get("kdv") or 20),
                               float(s.get("birim_fiyat") or 0) or None))
            s["urun_id"] = cur.lastrowid
            eslesme_ogren(con, cari_id, s.get("ad"), s["urun_id"])
        elif uid in (0, "0", "yok"):
            s["urun_id"] = 0
        elif uid not in (None, ""):
            try:
                s["urun_id"] = int(uid)
            except (TypeError, ValueError):
                s["urun_id"] = None
            if s["urun_id"]:
                eslesme_ogren(con, cari_id, s.get("ad"), s["urun_id"])
        else:
            s["urun_id"] = urun_bul(con, s.get("ad"), cari_id)
        sonuc.append(s)
    return sonuc


# ------------------------------------------------------------------ hareket yazma
def kaynak_sil(con, kaynak, kaynak_id):
    con.execute("DELETE FROM stok_hareketleri WHERE kaynak=? AND kaynak_id=?", (kaynak, kaynak_id))


def kaynak_yaz(con, kaynak, kaynak_id, tarih, satirlar, yon, tur):
    """Bir belgenin stok hareketlerini baştan yazar. yon: +1 giriş, -1 çıkış."""
    kaynak_sil(con, kaynak, kaynak_id)
    takipli = {r["id"] for r in con.execute("SELECT id FROM urunler WHERE stok_takibi=1")}
    for s in satirlar:
        uid = s.get("urun_id")
        try:
            miktar = float(s.get("miktar") or 0)
        except (TypeError, ValueError):
            miktar = 0
        if not uid or uid not in takipli or miktar <= 0:
            continue
        fiyat = s.get("matrah") and miktar and float(s["matrah"]) / miktar or s.get("birim_fiyat")
        try:
            fiyat = float(fiyat) if fiyat not in (None, "") else None
        except (TypeError, ValueError):
            fiyat = None
        con.execute("INSERT INTO stok_hareketleri(urun_id,tarih,tur,miktar,birim_fiyat,kaynak,kaynak_id,satir_ad) "
                    "VALUES(?,?,?,?,?,?,?,?)", (uid, tarih, tur, yon * miktar, fiyat, kaynak, kaynak_id, s.get("ad")))
        if yon > 0 and fiyat:
            con.execute("UPDATE urunler SET alis_fiyat=? WHERE id=?", (_k(fiyat), uid))


def irsaliye_stok_yaz(con, iid):
    i = con.execute("SELECT * FROM irsaliyeler WHERE id=?", (iid,)).fetchone()
    if not i or i["durum"] == "KONTROL":
        kaynak_sil(con, "irsaliye", iid)
        return
    kaynak_yaz(con, "irsaliye", iid, i["tarih"], json.loads(i["satirlar_json"] or "[]"), +1, "IRSALIYE")


def irsaliye_fiyatlari():
    """Faturayla eşleşmiş irsaliyelerin stok girişlerine faturadaki birim fiyatı işler (maliyet için)."""
    with db.islem() as con:
        eksik = con.execute(
            "SELECT h.id, h.satir_ad, h.urun_id, g.satirlar_json FROM stok_hareketleri h "
            "JOIN irsaliyeler i ON h.kaynak='irsaliye' AND i.id=h.kaynak_id "
            "JOIN gelen_faturalar g ON g.id=i.gelen_fatura_id WHERE h.birim_fiyat IS NULL").fetchall()
        for h in eksik:
            en_iyi, puan = None, 0
            hk = set(re.findall(r"[a-z0-9]{3,}", (h["satir_ad"] or "").translate(TR).lower()))
            for s in json.loads(h["satirlar_json"] or "[]"):
                sk = set(re.findall(r"[a-z0-9]{3,}", (s.get("ad") or "").translate(TR).lower()))
                p = len(hk & sk) / min(len(hk), len(sk)) if hk and sk else 0
                if p > puan:
                    en_iyi, puan = s, p
            if en_iyi and puan >= 0.5:
                try:
                    fiyat = float(en_iyi.get("birim_fiyat") or 0)
                except (TypeError, ValueError):
                    fiyat = 0
                if fiyat > 0:
                    con.execute("UPDATE stok_hareketleri SET birim_fiyat=? WHERE id=?", (fiyat, h["id"]))
                    con.execute("UPDATE urunler SET alis_fiyat=? WHERE id=?", (fiyat, h["urun_id"]))


# ------------------------------------------------------------------ hesaplar
def miktarlar(con):
    return {r["urun_id"]: _k(r["m"]) for r in con.execute(
        "SELECT urun_id, SUM(miktar) m FROM stok_hareketleri GROUP BY urun_id")}


def ortalama_maliyetler(con, bit=None):
    """Ağırlıklı ortalama alış maliyeti (fiyatı bilinen girişlerden); yoksa ürün kartındaki alış fiyatı."""
    sql = ("SELECT urun_id, SUM(miktar*birim_fiyat) t, SUM(miktar) m FROM stok_hareketleri "
           "WHERE miktar>0 AND birim_fiyat IS NOT NULL")
    p = []
    if bit:
        sql += " AND tarih<=?"
        p.append(bit)
    sonuc = {r["urun_id"]: r["t"] / r["m"] for r in con.execute(sql + " GROUP BY urun_id", p) if r["m"]}
    for u in con.execute("SELECT id, alis_fiyat FROM urunler WHERE alis_fiyat IS NOT NULL"):
        sonuc.setdefault(u["id"], u["alis_fiyat"])
    return sonuc


def kritik_sayisi():
    with db.islem() as con:
        m = miktarlar(con)
        return sum(1 for u in con.execute("SELECT id, kritik FROM urunler WHERE aktif=1 AND stok_takibi=1 AND kritik>0")
                   if m.get(u["id"], 0) <= u["kritik"])


