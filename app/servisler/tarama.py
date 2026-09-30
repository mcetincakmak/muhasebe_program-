"""Gelen e-fatura taraması: entegratörden yeni faturaları çeker, tedarikçiyi cari olarak tanımlar,
irsaliyelerle eşleştirir. Hem elle (API) hem günlük zamanlayıcıdan çağrılır."""
import json
from datetime import datetime

from .. import entegrator
from ..core import db
from ..core.ortak import TARAMA_KILIDI, hata
from .eslestirme import cari_bul_veya_olustur, eslestir
from .ubl import xml_ozet, xml_satirlar


def _gelen_kaydet(con, ent_id, xml):
    oz = xml_ozet(xml)
    if con.execute("SELECT 1 FROM gelen_faturalar WHERE uuid=?", (oz["uuid"],)).fetchone():
        return False
    cari_id = cari_bul_veya_olustur(con, oz["taraf"], "tedarikci", "efatura")
    con.execute(
        "INSERT INTO gelen_faturalar(uuid,fatura_no,gonderen_unvan,gonderen_vkn,tarih,tutar,para_birimi,entegrator_id,xml,"
        "cari_id,satirlar_json,irsaliye_nolar,kaynak,matrah,kdv_toplam,tip,kur,tevkifat_toplam) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (oz["uuid"], oz["fatura_no"], oz["gonderen_unvan"], oz["gonderen_vkn"], oz["tarih"], oz["tutar"],
         oz["para_birimi"], ent_id, xml, cari_id, json.dumps(xml_satirlar(xml), ensure_ascii=False),
         json.dumps(oz["irsaliye_nolar"]), "efatura", oz["matrah"], oz["kdv_toplam"], oz["tip"] or "SATIS",
         oz["kur"] if oz["para_birimi"] != "TRY" else 1, oz["tevkifat_toplam"]))
    return True


def tarama_yap():
    """Gelen e-faturaları çeker ve irsaliyelerle eşleştirir. Özet metin döndürür."""
    if not TARAMA_KILIDI.acquire(timeout=300):
        hata("Tarama zaten sürüyor.", 409)
    try:
        return _tarama_yap()
    finally:
        TARAMA_KILIDI.release()


def _tarama_yap():
    son = int(db.ayar_al("gelen_son_sira", "0") or 0)
    belgeler, yeni_son = entegrator.istemci(db.ayarlar_hepsi()).gelen_faturalar(son)
    eklenen, hatalar = 0, []
    with db.islem() as con:
        for ent_id, xml in belgeler:
            try:
                eklenen += _gelen_kaydet(con, ent_id, xml)
            except Exception as e:  # bozuk bir belge taramayı durdurmasın
                hatalar.append(f"Gelen belge okunamadı ({ent_id}): {e}")
    # Günlüğe işlem bittikten sonra yaz: açık yazma işlemi sürerken ikinci bağlantı veritabanını kilitli bulur
    for mesaj in hatalar:
        db.gunluge_yaz(mesaj)
    db.ayar_yaz({"gelen_son_sira": yeni_son, "son_tarama": datetime.now().isoformat(timespec="minutes")})
    otomatik, oneri = eslestir()
    ozet = f"{eklenen} yeni fatura, {otomatik} irsaliye otomatik eşleşti, {oneri} yeni öneri."
    db.gunluge_yaz("Tarama: " + ozet)
    return {"eklenen": eklenen, "otomatik": otomatik, "oneri": oneri, "mesaj": ozet}


