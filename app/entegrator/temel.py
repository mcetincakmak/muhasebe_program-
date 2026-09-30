"""Entegratör arayüzü.

Yeni bir özel entegratör (Uyumsoft, İzibiz, Logo vb.) eklemek için bu sınıftan türeyen bir dosya yazıp
entegrator/__init__.py içindeki KAYIT sözlüğüne eklemek yeterlidir; programın geri kalanı değişmez.
"""


class EntegratorHatasi(Exception):
    pass


class Entegrator:
    kod = ""
    ad = ""
    # Ayarlar ekranında gösterilecek alanlar: {"anahtar", "etiket", "tur": "metin"|"sifre", "varsayilan", "genis"}
    alanlar = []

    def __init__(self, ayarlar):
        self.ayarlar = ayarlar
        self.vkn = ayarlar.get("firma_vkn") or ""
        self.mod = ayarlar.get("ent_ortam") or "test"

    def efatura_mukellefi_mi(self, vkn):
        """(mükellef mi, posta kutusu etiketi)"""
        raise NotImplementedError

    def efatura_gonder(self, xml, fatura_no, alici_etiket=None):
        """{"id", "durum": GONDERILDI|ONAYLANDI, "aciklama"}"""
        raise NotImplementedError

    def earsiv_gonder(self, xml, fatura_no, uuid, alici_eposta=None):
        raise NotImplementedError

    def efatura_durum(self, belge_id):
        """{"durum", "aciklama"}"""
        raise NotImplementedError

    def gelen_faturalar(self, son_sira=0):
        """([(entegratör kimliği, UBL XML metni), ...], yeni son sıra)"""
        raise NotImplementedError

    def baglanti_testi(self):
        adimlar = []
        try:
            mukellef, etiket = self.efatura_mukellefi_mi(self.vkn)
            adimlar.append({"ad": "Servise bağlantı ve giriş", "ok": True})
            adimlar.append({"ad": "Firma e-Fatura mükellefi görünüyor mu", "ok": mukellef,
                            "not": etiket or ("" if mukellef else "Test ortamında mükellef kaydınız olmayabilir.")})
        except EntegratorHatasi as e:
            adimlar.append({"ad": "Servise bağlantı ve giriş", "ok": False, "not": str(e)})
        try:
            self.gelen_faturalar(int(self.ayarlar.get("gelen_son_sira") or 0))
            adimlar.append({"ad": "Gelen faturaları listeleme", "ok": True})
        except EntegratorHatasi as e:
            adimlar.append({"ad": "Gelen faturaları listeleme", "ok": False, "not": str(e)})
        return adimlar
