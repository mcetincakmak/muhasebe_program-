"""QNB eSolutions (eFinans) özel entegratör bağlantısı.

İki ortam vardır: test (QNB'nin test ortamı) ve canli (gerçek fatura).

ÖNEMLİ: Aşağıdaki servis/metot adları ve adresler QNB eSolutions'ın web servis
dokümantasyonuna göre DOĞRULANMALIDIR (qnbesolutions.com.tr > Destek > API Teknik).
Değişiklik gerekirse sadece bu dosyadaki METOTLAR ve ADRESLER kısmını düzenlemek yeterlidir.
"""
import base64
import hashlib
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape

import requests
from defusedxml.ElementTree import fromstring as guvenli_xml

from .temel import Entegrator, EntegratorHatasi

# ------------------------------------------------------------------ ADRESLER
VARSAYILAN_ADRESLER = {
    "test": {
        "efatura": "https://erpefaturatest1.qnbesolutions.com.tr/efatura/ws/connectorService",
        "earsiv": "https://earsivtest.qnbesolutions.com.tr/earsiv/ws/EarsivWebService",
    },
    "canli": {
        "efatura": "https://erpefatura.qnbesolutions.com.tr/efatura/ws/connectorService",
        "earsiv": "https://earsiv.qnbesolutions.com.tr/earsiv/ws/EarsivWebService",
    },
}

# ------------------------------------------------------------------ METOTLAR
NS_EFATURA = "http://service.connector.uut.cs.com.tr/"
NS_EARSIV = "http://service.earsiv.uut.cs.com.tr/"




def _zip_b64(dosya_adi, icerik):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(dosya_adi, icerik)
    return base64.b64encode(buf.getvalue()).decode()


def _yerel(el):
    return el.tag.split("}")[-1]


def _ara(root, ad):
    return [el for el in root.iter() if _yerel(el) == ad]


class QNB(Entegrator):
    kod = "qnb"
    ad = "QNB eSolutions (eFinans)"
    alanlar = [
        {"anahtar": "ent_kullanici", "etiket": "Web servis kullanıcı adı"},
        {"anahtar": "ent_sifre", "etiket": "Web servis şifresi", "tur": "sifre"},
        {"anahtar": "qnb_sube", "etiket": "e-Arşiv şube kodu", "varsayilan": "DFLT"},
        {"anahtar": "qnb_kasa", "etiket": "e-Arşiv kasa kodu", "varsayilan": "DFLT"},
        {"anahtar": "qnb_url_efatura", "etiket": "e-Fatura servis adresi (boşsa varsayılan)", "genis": True},
        {"anahtar": "qnb_url_earsiv", "etiket": "e-Arşiv servis adresi (boşsa varsayılan)", "genis": True},
    ]

    def __init__(self, ayarlar):
        super().__init__(ayarlar)
        self.mod = "canli" if ayarlar.get("ent_ortam") == "canli" else "test"
        self.kullanici = ayarlar.get("ent_kullanici") or ""
        self.sifre = ayarlar.get("ent_sifre") or ""
        self.vkn = ayarlar.get("firma_vkn") or ""
        self.sube = ayarlar.get("qnb_sube") or "DFLT"
        self.kasa = ayarlar.get("qnb_kasa") or "DFLT"
        adr = VARSAYILAN_ADRESLER.get(self.mod, {})
        self.url_efatura = ayarlar.get("qnb_url_efatura") or adr.get("efatura", "")
        self.url_earsiv = ayarlar.get("qnb_url_earsiv") or adr.get("earsiv", "")


    # -------------------------------------------------------------- SOAP
    def _soap(self, url, ns, metot, govde_xml):
        if not (self.kullanici and self.sifre):
            raise EntegratorHatasi("QNB kullanıcı adı ve şifresi Ayarlar'da girilmemiş.")
        zarf = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="{ns}">
<soapenv:Header><wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<wsse:UsernameToken><wsse:Username>{escape(self.kullanici)}</wsse:Username><wsse:Password>{escape(self.sifre)}</wsse:Password></wsse:UsernameToken>
</wsse:Security></soapenv:Header>
<soapenv:Body><ser:{metot}>{govde_xml}</ser:{metot}></soapenv:Body></soapenv:Envelope>"""
        try:
            r = requests.post(url, data=zarf.encode("utf-8"), timeout=60,
                              headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""})
        except requests.RequestException as e:
            raise EntegratorHatasi(f"QNB'ye bağlanılamadı: {e}")
        try:
            root = guvenli_xml(r.content)
        except ET.ParseError:
            raise EntegratorHatasi(f"QNB beklenmeyen bir yanıt döndü (HTTP {r.status_code}).")
        hata = _ara(root, "faultstring")
        if hata:
            raise EntegratorHatasi(f"QNB hatası: {hata[0].text}")
        if r.status_code >= 400:
            raise EntegratorHatasi(f"QNB HTTP {r.status_code} döndü.")
        return root

    # -------------------------------------------------------------- Mükellef sorgusu
    def efatura_mukellefi_mi(self, vkn):
        """(mükellef mi, posta kutusu etiketi) döndürür."""
        vkn = (vkn or "").strip()
        root = self._soap(self.url_efatura, NS_EFATURA, "efaturaKullanicisi",
                          f"<vergiTcKimlikNo>{escape(vkn)}</vergiTcKimlikNo>")
        ret = _ara(root, "return")
        mukellef = bool(ret) and (ret[0].text or "").strip().lower() == "true"
        etiket = None
        if mukellef:
            try:
                root2 = self._soap(self.url_efatura, NS_EFATURA, "efaturaKullaniciBilgisi",
                                   f"<vergiTcKimlikNo>{escape(vkn)}</vergiTcKimlikNo>")
                pk = [e.text for e in _ara(root2, "etiket") if e.text and "pk" in e.text.lower()]
                etiket = pk[0] if pk else None
            except EntegratorHatasi:
                pass  # Etiket alınamazsa QNB varsayılan posta kutusunu kullanır.
        return mukellef, etiket

    # -------------------------------------------------------------- Gönderim
    def efatura_gonder(self, xml, fatura_no, alici_etiket=None):
        veri = _zip_b64(f"{fatura_no}.xml", xml.encode("utf-8"))
        md5 = hashlib.md5(base64.b64decode(veri), usedforsecurity=False).hexdigest().upper()  # QNB belge özeti, güvenlik amaçlı değil
        govde = (f"<vergiTcKimlikNo>{self.vkn}</vergiTcKimlikNo><belgeTuru>FATURA_UBL</belgeTuru>"
                 f"<belgeNo>{fatura_no}</belgeNo><veri>{veri}</veri><belgeHash>{md5}</belgeHash>"
                 f"<mimeType>application/zip</mimeType><belgeVersiyon>3.0</belgeVersiyon>")
        if alici_etiket:
            govde += f"<aliciEtiket>{escape(alici_etiket)}</aliciEtiket>"
        root = self._soap(self.url_efatura, NS_EFATURA, "belgeGonder", govde)
        ret = _ara(root, "return")
        return {"id": ret[0].text if ret else "", "durum": "GONDERILDI",
                "aciklama": "QNB'ye iletildi, GİB yanıtı bekleniyor."}

    def earsiv_gonder(self, xml, fatura_no, uuid, alici_eposta=None):
        giris = {"islemId": uuid, "vkn": self.vkn, "sube": self.sube, "kasa": self.kasa,
                 "donenBelgeFormati": "3", "numaraVerilsinMi": 0}
        if alici_eposta:
            giris["eArsivFaturaGonderimi"] = {"email": alici_eposta}
        govde = (f"<input>{escape(json.dumps(giris, ensure_ascii=False))}</input>"
                 f"<fatura><belgeFormati>UBL</belgeFormati>"
                 f"<belgeIcerigi>{base64.b64encode(xml.encode('utf-8')).decode()}</belgeIcerigi></fatura>")
        root = self._soap(self.url_earsiv, NS_EARSIV, "faturaOlustur", govde)
        sonuc = _ara(root, "resultCode")
        kod = sonuc[0].text if sonuc else ""
        if kod and kod != "AE00000":
            aciklama = _ara(root, "resultText")
            raise EntegratorHatasi(f"e-Arşiv hatası ({kod}): {aciklama[0].text if aciklama else ''}")
        return {"id": uuid, "durum": "ONAYLANDI", "aciklama": "e-Arşiv fatura oluşturuldu."}

    # -------------------------------------------------------------- Durum sorgu
    def efatura_durum(self, belge_id):
        root = self._soap(self.url_efatura, NS_EFATURA, "gidenBelgeDurumSorgula",
                          f"<vergiTcKimlikNo>{self.vkn}</vergiTcKimlikNo><belgeOid>{escape(belge_id)}</belgeOid>")
        durum = _ara(root, "durum")
        aciklama = _ara(root, "aciklama")
        kod = (durum[0].text or "") if durum else ""
        gib = _ara(root, "gonderimDurumu")
        gib_kod = (gib[0].text or "") if gib else ""
        # QNB kodları dokümantasyona göre eşlenmeli; bilinmeyen durumlar olduğu gibi gösterilir.
        if kod in ("3",) or gib_kod in ("4",):
            sonuc = "ONAYLANDI"
        elif kod in ("2",) or gib_kod in ("-1", "5"):
            sonuc = "HATA"
        else:
            sonuc = "GONDERILDI"
        return {"durum": sonuc,
                "aciklama": (aciklama[0].text if aciklama else "") or f"QNB durum kodu: {kod}/{gib_kod}"}

    # -------------------------------------------------------------- Gelen faturalar
    def gelen_faturalar(self, son_sira=0):
        """[(entegrator_id, xml_metni), ...] ve yeni son sıra numarasını döndürür."""
        root = self._soap(self.url_efatura, NS_EFATURA, "gelenBelgeleriListele",
                          f"<parametreler><vergiTcKimlikNo>{self.vkn}</vergiTcKimlikNo>"
                          f"<sonAlinanBelgeSiraNumarasi>{int(son_sira)}</sonAlinanBelgeSiraNumarasi>"
                          f"<belgeTuru>FATURA</belgeTuru></parametreler>")
        sonuc, yeni_sira = [], son_sira
        for belge in _ara(root, "return"):
            ett = next((e.text for e in belge.iter() if _yerel(e) == "ettn"), None)
            sira = next((e.text for e in belge.iter() if _yerel(e) == "belgeSiraNo"), None)
            if sira and sira.isdigit():
                yeni_sira = max(yeni_sira, int(sira))
            if not ett:
                continue
            r2 = self._soap(self.url_efatura, NS_EFATURA, "gelenBelgeleriIndir",
                            f"<vergiTcKimlikNo>{self.vkn}</vergiTcKimlikNo><ettnler>{escape(ett)}</ettnler>"
                            f"<belgeTuru>FATURA</belgeTuru><belgeFormati>UBL</belgeFormati>")
            for veri in _ara(r2, "return"):
                ham = base64.b64decode(veri.text or "")
                if ham[:2] == b"PK":
                    with zipfile.ZipFile(io.BytesIO(ham)) as z:
                        for bilgi in z.infolist():
                            if bilgi.filename.lower().endswith(".xml") and bilgi.file_size <= 20 * 1024 * 1024:
                                sonuc.append((ett, z.read(bilgi).decode("utf-8")))
                else:
                    sonuc.append((ett, ham.decode("utf-8")))
        return sonuc, yeni_sira
