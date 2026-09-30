"""Deneme entegratörü: hiçbir yere bağlanmaz, her şeyi taklit eder. Programı tanımak ve test için."""
import uuid as uuidlib
from datetime import datetime

from .temel import Entegrator


class Deneme(Entegrator):
    kod = "deneme"
    ad = "Deneme modu (gerçek fatura kesilmez)"
    alanlar = []

    def efatura_mukellefi_mi(self, vkn):
        vkn = (vkn or "").strip()  # 10 haneli VKN mükellef, 11 haneli TCKN değil sayılır
        return (len(vkn) == 10, f"urn:mail:defaultpk@deneme-{vkn}.com" if len(vkn) == 10 else None)

    def efatura_gonder(self, xml, fatura_no, alici_etiket=None):
        return {"id": "DENEME-" + uuidlib.uuid4().hex[:12], "durum": "GONDERILDI",
                "aciklama": "Deneme modu: fatura GİB'e iletilmiş gibi işaretlendi."}

    def earsiv_gonder(self, xml, fatura_no, uuid, alici_eposta=None):
        return {"id": "DENEME-" + uuidlib.uuid4().hex[:12], "durum": "ONAYLANDI",
                "aciklama": "Deneme modu: e-Arşiv fatura oluşturulmuş gibi işaretlendi."}

    def efatura_durum(self, belge_id):
        return {"durum": "ONAYLANDI", "aciklama": "Deneme modu: alıcıya ulaştı."}

    def gelen_faturalar(self, son_sira=0):
        return _ornek_gelenler(), son_sira


def _ornek_gelenler():
    """Deneme modunda gösterilecek örnek gelen faturalar."""
    from ..servisler.ubl import fatura_xml
    ornekler = [
        ("Göl Kırtasiye ve Büro Malzemeleri San. Tic. Ltd. Şti.", "3950123456", "GKF2026000000014",
         [{"ad": "A4 Fotokopi Kağıdı 80gr", "miktar": 3, "birim": "BX", "birim_fiyat": 850, "kdv": 20},
          {"ad": "Tükenmez Kalem Mavi", "miktar": 50, "birim": "C62", "birim_fiyat": 12, "kdv": 20},
          {"ad": "Klasör Geniş", "miktar": 12, "birim": "C62", "birim_fiyat": 45, "kdv": 20}],
         [{"no": "GKI2026000000031", "tarih": datetime.now().strftime("%Y-%m-%d")}]),
        ("Göller Bölgesi Telekom A.Ş.", "9876543210", "GBT2026000001207",
         [{"ad": "İnternet hizmeti", "miktar": 1, "birim": "MON", "birim_fiyat": 749.9, "kdv": 20}], []),
    ]
    liste = []
    bugun = datetime.now().strftime("%Y-%m-%d")
    for unvan, vkn, no, satirlar, irsaliyeler in ornekler:
        u = str(uuidlib.uuid5(uuidlib.NAMESPACE_DNS, no))
        xml = fatura_xml(
            {"fatura_no": no, "uuid": u, "tip": "EFATURA", "senaryo": "TEMELFATURA",
             "tarih": bugun, "saat": "10:00:00", "satirlar": satirlar, "irsaliyeler": irsaliyeler},
            {"unvan": unvan, "vkn": vkn, "il": "Burdur", "ilce": "Merkez", "vergi_dairesi": "Burdur"},
            {"unvan": "Sizin Firmanız", "vkn": "1111111111", "il": "Burdur", "ilce": "Merkez"},
        )
        liste.append(("DENEME-" + no, xml))
    return liste
