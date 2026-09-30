"""İrsaliye ile gelen faturaları eşleştirir; tedarikçileri otomatik cari olarak tanımlar.

Puanlama:
  100  Faturada irsaliye numarası birebir geçiyor  -> otomatik birleştirilir
  50-89 Aynı tedarikçi, yakın tarih, ürünler benzer -> öneri olarak gösterilir, kullanıcı onaylar
"""
import json
import re
from datetime import date

from ..core import db

OTOMATIK_ESIK = 90
ONERI_ESIK = 50
TR = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUcgiiosu")


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").translate(TR).upper())


def _kelimeler(s):
    return {k for k in re.findall(r"[a-z0-9]{3,}", (s or "").translate(TR).lower())}


def _unvan_benzer(a, b):
    ka, kb = _kelimeler(a) - {"ltd", "sti", "san", "tic", "limited", "sirketi", "ve"}, \
        _kelimeler(b) - {"ltd", "sti", "san", "tic", "limited", "sirketi", "ve"}
    return bool(ka and kb) and len(ka & kb) / min(len(ka), len(kb)) >= 0.6


def _gun(t):
    try:
        return date.fromisoformat(t)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ cari
def cari_bul_veya_olustur(con, taraf, tur="tedarikci", kaynak="foto"):
    """taraf: unvan, vkn, vergi_dairesi, adres, ilce, il, telefon, eposta. cari id döndürür."""
    vkn = re.sub(r"\D", "", taraf.get("vkn") or "")
    unvan = (taraf.get("unvan") or "").strip()
    if not vkn and not unvan:
        return None
    r = None
    if vkn:
        r = con.execute("SELECT * FROM cariler WHERE vkn=?", (vkn,)).fetchone()
    if not r and unvan:
        for c in con.execute("SELECT * FROM cariler"):
            if _unvan_benzer(c["unvan"], unvan) and (not vkn or not c["vkn"]):
                r = c
                break
    if r:
        guncel = {}
        if r["tur"] not in (tur, "ikisi"):
            guncel["tur"] = "ikisi"
        for k in ("vkn", "vergi_dairesi", "adres", "ilce", "il", "telefon", "eposta"):
            deger = vkn if k == "vkn" else (taraf.get(k) or "").strip()
            if deger and not r[k]:
                guncel[k] = deger
        # Fotoğraftan otomatik açılmış carinin ünvanını e-faturadaki doğru ünvanla düzelt
        if kaynak == "efatura" and unvan and (r["notlar"] or "").startswith("Otomatik") and r["unvan"] != unvan:
            guncel["unvan"] = unvan
            guncel["notlar"] = "Otomatik tanımlandı (e-faturadan)"
            con.execute("UPDATE irsaliyeler SET gonderen_unvan=? WHERE cari_id=?", (unvan, r["id"]))
        if guncel:
            con.execute(f"UPDATE cariler SET {','.join(k + '=?' for k in guncel)} WHERE id=?",
                        list(guncel.values()) + [r["id"]])
        return r["id"]
    cur = con.execute(
        "INSERT INTO cariler(unvan,vkn,vergi_dairesi,adres,ilce,il,telefon,eposta,tur,notlar) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (unvan or f"VKN {vkn}", vkn, taraf.get("vergi_dairesi") or "", taraf.get("adres") or "",
         taraf.get("ilce") or "", taraf.get("il") or "", taraf.get("telefon") or "", taraf.get("eposta") or "",
         tur, "Otomatik tanımlandı (e-faturadan)" if kaynak == "efatura" else "Otomatik tanımlandı (fotoğraftan)"))
    return cur.lastrowid


# ------------------------------------------------------------------ puanlama
def puanla(irs, fat):
    """(puan, açıklama)"""
    irs_no = _norm(irs["irsaliye_no"])
    fat_nolar = {_norm(n) for n in json.loads(fat["irsaliye_nolar"] or "[]")}
    if irs_no and irs_no in fat_nolar:
        return 100, "Faturada irsaliye numarası geçiyor"

    ayni_tedarikci = (irs["gonderen_vkn"] and irs["gonderen_vkn"] == fat["gonderen_vkn"]) or \
                     (irs["cari_id"] and irs["cari_id"] == fat["cari_id"]) or \
                     _unvan_benzer(irs["gonderen_unvan"], fat["gonderen_unvan"])
    if not ayni_tedarikci:
        return 0, ""
    # Faturada başka irsaliye numaraları varsa ve bu irsaliye yoksa, büyük ihtimalle başka faturadır
    if fat_nolar and irs_no:
        return 0, ""

    puan, neden = 30, ["aynı tedarikçi"]
    di, df = _gun(irs["tarih"]), _gun(fat["tarih"])
    if di and df:
        fark = (df - di).days
        if fark < -3 or fark > 45:
            return 0, ""
        if 0 <= fark <= 7:
            puan += 20
            neden.append(f"fatura irsaliyeden {fark} gün sonra")
        else:
            puan += 5

    i_satir = json.loads(irs["satirlar_json"] or "[]")
    f_satir = json.loads(fat["satirlar_json"] or "[]")
    if i_satir and f_satir:
        uyan = 0
        for s in i_satir:
            ks = _kelimeler(s.get("ad"))
            for f in f_satir:
                kf = _kelimeler(f.get("ad"))
                if ks and kf and len(ks & kf) / min(len(ks), len(kf)) >= 0.5:
                    try:
                        miktar_ayni = abs(float(s.get("miktar") or 0) - float(f.get("miktar") or 0)) < 0.001
                    except ValueError:
                        miktar_ayni = False
                    uyan += 1 if miktar_ayni else 0.6
                    break
        oran = uyan / len(i_satir)
        puan += int(oran * 39)
        if oran:
            neden.append(f"ürünlerin %{int(oran * 100)}'i uyuşuyor")
    return min(puan, 89), ", ".join(neden)


# ------------------------------------------------------------------ eşleştir
def _esle():
    """Bekleyen irsaliyeleri gelen faturalarla eşleştirir. (otomatik, öneri) sayılarını döndürür."""
    otomatik = oneri = 0
    with db.islem() as con:
        irsaliyeler = con.execute("SELECT * FROM irsaliyeler WHERE durum IN ('BEKLIYOR','ONERI')").fetchall()
        faturalar = con.execute("SELECT * FROM gelen_faturalar WHERE COALESCE(tip,'SATIS') != 'IADE'").fetchall()
        for irs in irsaliyeler:
            en_iyi, en_puan, en_neden = None, 0, ""
            for fat in faturalar:
                if fat["id"] in set(json.loads(irs["reddedilen_json"] or "[]")):
                    continue
                p, n = puanla(irs, fat)
                if p > en_puan:
                    en_iyi, en_puan, en_neden = fat, p, n
            if en_iyi and en_puan >= OTOMATIK_ESIK:
                con.execute("UPDATE irsaliyeler SET durum='ESLESTI', gelen_fatura_id=?, oneri_fatura_id=NULL, "
                            "eslesme_puani=?, eslesme_aciklama=? WHERE id=?",
                            (en_iyi["id"], en_puan, en_neden, irs["id"]))
                otomatik += 1
            elif en_iyi and en_puan >= ONERI_ESIK:
                if irs["oneri_fatura_id"] != en_iyi["id"]:
                    oneri += 1
                con.execute("UPDATE irsaliyeler SET durum='ONERI', oneri_fatura_id=?, eslesme_puani=?, "
                            "eslesme_aciklama=? WHERE id=?", (en_iyi["id"], en_puan, en_neden, irs["id"]))
    return otomatik, oneri



def eslestir():
    """Eşleştirir, ardından eşleşen irsaliyelerin stok girişlerine faturadaki fiyatları işler."""
    from . import stok
    sonuc = _esle()
    stok.irsaliye_fiyatlari()
    return sonuc
