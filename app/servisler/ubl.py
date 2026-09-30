"""Fatura tutar hesabı ve UBL-TR 1.2 (UBL 2.1) XML üretimi.

Not: XML'deki mali mühür imzası (UBLExtensions içine) özel entegratör (QNB) tarafından eklenir.
"""
import re
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import fromstring as guvenli_xml  # dışarıdan gelen XML için (XML bombası vb.)
from decimal import Decimal, ROUND_HALF_UP

NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
for _p, _u in NS.items():
    ET.register_namespace(_p, _u)

BIRIMLER = {
    "C62": "Adet", "HUR": "Saat", "DAY": "Gün", "MON": "Ay", "KGM": "Kg",
    "LTR": "Litre", "MTR": "Metre", "MTK": "m²", "SET": "Set", "BX": "Kutu",
}

KURUS = Decimal("0.01")

# KDV tevkifat kodları: kod -> (açıklama, tevkif oranı pay/10). Güncel liste ve oranları mali müşavirinizle teyit edin.
TEVKIFAT_KODLARI = {
    "601": ("Yapım işleri ile birlikte ifa edilen mühendislik-mimarlık ve etüt-proje hizmetleri", 4),
    "602": ("Etüt, plan-proje, danışmanlık, denetim ve benzeri hizmetler", 9),
    "603": ("Makine, teçhizat, demirbaş ve taşıtlara ait tadil, bakım ve onarım hizmetleri", 7),
    "604": ("Yemek servis hizmeti", 5),
    "605": ("Organizasyon hizmeti", 5),
    "606": ("İşgücü temin hizmetleri", 9),
    "607": ("Özel güvenlik hizmeti", 9),
    "608": ("Yapı denetim hizmetleri", 9),
    "609": ("Fason olarak yaptırılan tekstil ve konfeksiyon işleri", 7),
    "612": ("Temizlik hizmeti", 9),
    "613": ("Çevre ve bahçe bakım hizmetleri", 9),
    "614": ("Servis taşımacılığı hizmeti", 5),
    "615": ("Her türlü baskı ve basım hizmetleri", 7),
    "616": ("Diğer hizmetler (5018 sayılı kanun kapsamındaki idarelere)", 5),
    "624": ("Yük taşımacılığı hizmeti", 2),
    "625": ("Ticari reklam hizmetleri", 3),
}
PARA_BIRIMLERI = ("TRY", "USD", "EUR", "GBP")


def d(x):
    return Decimal(str(x if x not in (None, "") else 0))


def yuvarla(x):
    return d(x).quantize(KURUS, rounding=ROUND_HALF_UP)


def hesapla(satirlar):
    """Her satır: ad, miktar, birim, birim_fiyat, iskonto (%), kdv (%). Hesaplanmış kopyayı döndürür."""
    sonuc, kdv_gruplari, tev_gruplari = [], {}, {}
    brut_t = isk_t = matrah_t = kdv_t = tev_t = Decimal(0)
    for s in satirlar:
        miktar, fiyat = d(s.get("miktar", 1)), d(s.get("birim_fiyat", 0))
        isk_oran, kdv_oran = d(s.get("iskonto", 0)), d(s.get("kdv", 20))
        brut = yuvarla(miktar * fiyat)
        isk = yuvarla(brut * isk_oran / 100)
        matrah = brut - isk
        kdv = yuvarla(matrah * kdv_oran / 100)
        kod = str(s.get("tevkifat_kod") or "")
        tev = yuvarla(kdv * TEVKIFAT_KODLARI[kod][1] / 10) if kod in TEVKIFAT_KODLARI else Decimal(0)
        yeni = dict(s)
        yeni.update(brut=float(brut), iskonto_tutar=float(isk), matrah=float(matrah),
                    kdv_tutar=float(kdv), tevkifat_kod=kod if tev or kod in TEVKIFAT_KODLARI else "",
                    tevkifat_tutar=float(tev), toplam=float(matrah + kdv - tev))
        sonuc.append(yeni)
        brut_t += brut; isk_t += isk; matrah_t += matrah; kdv_t += kdv; tev_t += tev
        if kod in TEVKIFAT_KODLARI:
            t = tev_gruplari.setdefault(kod, [Decimal(0), Decimal(0)])
            t[0] += kdv; t[1] += tev
        g = kdv_gruplari.setdefault(str(kdv_oran.normalize()), [Decimal(0), Decimal(0)])
        g[0] += matrah; g[1] += kdv
    return {
        "satirlar": sonuc,
        "brut_toplam": float(brut_t), "iskonto_toplam": float(isk_t), "matrah": float(matrah_t),
        "kdv_toplam": float(kdv_t), "tevkifat_toplam": float(tev_t),
        "vergili_toplam": float(matrah_t + kdv_t), "genel_toplam": float(matrah_t + kdv_t - tev_t),
        "kdv_gruplari": {k: [float(v[0]), float(v[1])] for k, v in kdv_gruplari.items()},
        "tevkifat_gruplari": {k: [float(v[0]), float(v[1])] for k, v in tev_gruplari.items()},
    }


# ---------------------------------------------------------------- XML yardımcıları
def _e(parent, tag, text=None, **attrs):
    pfx, name = tag.split(":") if ":" in tag else ("", tag)
    el = ET.SubElement(parent, f"{{{NS[pfx]}}}{name}", {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _tutar(parent, tag, deger, para):
    return _e(parent, tag, f"{yuvarla(deger):.2f}", currencyID=para)


def _kimlik_tipi(no):
    return "TCKN" if len((no or "").strip()) == 11 else "VKN"


def _taraf(parent, bilgi, imza_icin=False):
    return _taraf_icerik(_e(parent, "cac:Party"), bilgi, imza_icin)


def _taraf_icerik(party, bilgi, imza_icin=False):
    no = (bilgi.get("vkn") or "").strip()
    _e(_e(party, "cac:PartyIdentification"), "cbc:ID", no, schemeID=_kimlik_tipi(no))
    if bilgi.get("mersis") and not imza_icin:
        _e(_e(party, "cac:PartyIdentification"), "cbc:ID", bilgi["mersis"], schemeID="MERSISNO")
    if not imza_icin:
        _e(_e(party, "cac:PartyName"), "cbc:Name", bilgi.get("unvan", ""))
    adr = _e(party, "cac:PostalAddress")
    if bilgi.get("adres"):
        _e(adr, "cbc:StreetName", bilgi["adres"])
    _e(adr, "cbc:CitySubdivisionName", bilgi.get("ilce") or "-")
    _e(adr, "cbc:CityName", bilgi.get("il") or "-")
    _e(_e(adr, "cac:Country"), "cbc:Name", bilgi.get("ulke") or "Türkiye")
    if imza_icin:
        return party
    if bilgi.get("vergi_dairesi"):
        _e(_e(_e(party, "cac:PartyTaxScheme"), "cac:TaxScheme"), "cbc:Name", bilgi["vergi_dairesi"])
    if bilgi.get("telefon") or bilgi.get("eposta"):
        c = _e(party, "cac:Contact")
        if bilgi.get("telefon"):
            _e(c, "cbc:Telephone", bilgi["telefon"])
        if bilgi.get("eposta"):
            _e(c, "cbc:ElectronicMail", bilgi["eposta"])
    if _kimlik_tipi(no) == "TCKN":
        p = _e(party, "cac:Person")
        ad = bilgi.get("ad") or (bilgi.get("unvan", "").rsplit(" ", 1)[0])
        soyad = bilgi.get("soyad") or (bilgi.get("unvan", "").rsplit(" ", 1)[-1])
        _e(p, "cbc:FirstName", ad)
        _e(p, "cbc:FamilyName", soyad)
    return party


def _vergi(parent, matrah, kdv, oran, para):
    tt = _e(parent, "cac:TaxTotal")
    _tutar(tt, "cbc:TaxAmount", kdv, para)
    ts = _e(tt, "cac:TaxSubtotal")
    _tutar(ts, "cbc:TaxableAmount", matrah, para)
    _tutar(ts, "cbc:TaxAmount", kdv, para)
    _e(ts, "cbc:Percent", f"{d(oran).normalize():f}")
    cat = _e(ts, "cac:TaxCategory")
    if d(oran) == 0:
        # Varsayılan istisna kodu; farklı bir istisna uyguluyorsanız mali müşavirinize danışın.
        _e(cat, "cbc:TaxExemptionReasonCode", "351")
        _e(cat, "cbc:TaxExemptionReason", "İstisna Olmayan Diğer")
    sch = _e(cat, "cac:TaxScheme")
    _e(sch, "cbc:Name", "KDV")
    _e(sch, "cbc:TaxTypeCode", "0015")
    return tt


def _tevkifat_alt(parent, kod, kdv, tev, para):
    ts = _e(parent, "cac:TaxSubtotal")
    _tutar(ts, "cbc:TaxableAmount", kdv, para)
    _tutar(ts, "cbc:TaxAmount", tev, para)
    _e(ts, "cbc:Percent", TEVKIFAT_KODLARI[kod][1] * 10)
    sch = _e(_e(ts, "cac:TaxCategory"), "cac:TaxScheme")
    _e(sch, "cbc:Name", TEVKIFAT_KODLARI[kod][0])
    _e(sch, "cbc:TaxTypeCode", kod)


def fatura_xml(fatura, firma, cari):
    """fatura: fatura_no, uuid, tip (EFATURA/EARSIV), senaryo, tarih, saat, satirlar, notlar, para_birimi."""
    para = fatura.get("para_birimi") or "TRY"
    h = hesapla(fatura["satirlar"])
    earsiv = fatura["tip"] == "EARSIV"

    inv = ET.Element(f"{{{NS['']}}}Invoice")
    _e(_e(_e(inv, "ext:UBLExtensions"), "ext:UBLExtension"), "ext:ExtensionContent")
    _e(inv, "cbc:UBLVersionID", "2.1")
    _e(inv, "cbc:CustomizationID", "TR1.2")
    _e(inv, "cbc:ProfileID", "EARSIVFATURA" if earsiv else (fatura.get("senaryo") or "TEMELFATURA"))
    _e(inv, "cbc:ID", fatura["fatura_no"])
    _e(inv, "cbc:CopyIndicator", "false")
    _e(inv, "cbc:UUID", fatura["uuid"])
    _e(inv, "cbc:IssueDate", fatura["tarih"])
    _e(inv, "cbc:IssueTime", fatura.get("saat") or "12:00:00")
    iade = fatura.get("fatura_turu") == "IADE"
    _e(inv, "cbc:InvoiceTypeCode", "IADE" if iade else ("TEVKIFAT" if h["tevkifat_toplam"] else "SATIS"))
    if earsiv:
        _e(inv, "cbc:Note", "Gönderim Şekli: ELEKTRONIK")
    for n in (fatura.get("notlar") or "").splitlines():
        if n.strip():
            _e(inv, "cbc:Note", n.strip())
    _e(inv, "cbc:DocumentCurrencyCode", para)
    _e(inv, "cbc:LineCountNumeric", len(h["satirlar"]))
    if iade:
        for ref in fatura.get("iade_ref") or []:
            idr = _e(_e(inv, "cac:BillingReference"), "cac:InvoiceDocumentReference")
            _e(idr, "cbc:ID", ref["no"])
            _e(idr, "cbc:IssueDate", ref["tarih"])
            _e(idr, "cbc:DocumentTypeCode", "IADE")
    for irs in fatura.get("irsaliyeler") or []:
        ddr = _e(inv, "cac:DespatchDocumentReference")
        _e(ddr, "cbc:ID", irs["no"])
        _e(ddr, "cbc:IssueDate", irs["tarih"])
    if earsiv:
        adr = _e(inv, "cac:AdditionalDocumentReference")
        _e(adr, "cbc:ID", "ELEKTRONIK")
        _e(adr, "cbc:IssueDate", fatura["tarih"])
        _e(adr, "cbc:DocumentTypeCode", "SEND_TYPE")

    sig = _e(inv, "cac:Signature")
    _e(sig, "cbc:ID", firma.get("vkn", ""), schemeID="VKN_TCKN")
    _taraf_icerik(_e(sig, "cac:SignatoryParty"), firma, imza_icin=True)
    _e(_e(_e(sig, "cac:DigitalSignatureAttachment"), "cac:ExternalReference"), "cbc:URI", "#Signature")

    _taraf(_e(inv, "cac:AccountingSupplierParty"), firma)
    _taraf(_e(inv, "cac:AccountingCustomerParty"), cari)
    if fatura.get("vade_tarihi"):
        pm = _e(inv, "cac:PaymentMeans")
        _e(pm, "cbc:PaymentMeansCode", "1")  # UN/ECE 4461: tanımsız ödeme şekli
        _e(pm, "cbc:PaymentDueDate", fatura["vade_tarihi"])
    if para != "TRY":
        per = _e(inv, "cac:PricingExchangeRate")
        _e(per, "cbc:SourceCurrencyCode", para)
        _e(per, "cbc:TargetCurrencyCode", "TRY")
        _e(per, "cbc:CalculationRate", f"{d(fatura.get('kur') or 1).normalize():f}")
        _e(per, "cbc:Date", fatura["tarih"])

    # Belge vergi toplamı
    tt = _e(inv, "cac:TaxTotal")
    _tutar(tt, "cbc:TaxAmount", h["kdv_toplam"], para)
    for oran, (matrah, kdv) in sorted(h["kdv_gruplari"].items(), key=lambda x: d(x[0])):
        ts = _e(tt, "cac:TaxSubtotal")
        _tutar(ts, "cbc:TaxableAmount", matrah, para)
        _tutar(ts, "cbc:TaxAmount", kdv, para)
        _e(ts, "cbc:Percent", oran)
        cat = _e(ts, "cac:TaxCategory")
        if d(oran) == 0:
            _e(cat, "cbc:TaxExemptionReasonCode", "351")
            _e(cat, "cbc:TaxExemptionReason", "İstisna Olmayan Diğer")
        sch = _e(cat, "cac:TaxScheme")
        _e(sch, "cbc:Name", "KDV")
        _e(sch, "cbc:TaxTypeCode", "0015")

    if h["tevkifat_toplam"]:
        wt = _e(inv, "cac:WithholdingTaxTotal")
        _tutar(wt, "cbc:TaxAmount", h["tevkifat_toplam"], para)
        for kod, (kdv, tev) in sorted(h["tevkifat_gruplari"].items()):
            _tevkifat_alt(wt, kod, kdv, tev, para)

    lmt = _e(inv, "cac:LegalMonetaryTotal")
    _tutar(lmt, "cbc:LineExtensionAmount", h["brut_toplam"], para)
    _tutar(lmt, "cbc:TaxExclusiveAmount", h["matrah"], para)
    _tutar(lmt, "cbc:TaxInclusiveAmount", h["vergili_toplam"], para)
    _tutar(lmt, "cbc:AllowanceTotalAmount", h["iskonto_toplam"], para)
    _tutar(lmt, "cbc:PayableAmount", h["genel_toplam"], para)

    for i, s in enumerate(h["satirlar"], 1):
        ln = _e(inv, "cac:InvoiceLine")
        _e(ln, "cbc:ID", i)
        _e(ln, "cbc:InvoicedQuantity", f"{d(s.get('miktar', 1)).normalize():f}", unitCode=s.get("birim") or "C62")
        _tutar(ln, "cbc:LineExtensionAmount", s["matrah"], para)
        if s["iskonto_tutar"]:
            ac = _e(ln, "cac:AllowanceCharge")
            _e(ac, "cbc:ChargeIndicator", "false")
            _e(ac, "cbc:MultiplierFactorNumeric", f"{d(s.get('iskonto', 0)) / 100:f}")
            _tutar(ac, "cbc:Amount", s["iskonto_tutar"], para)
            _tutar(ac, "cbc:BaseAmount", s["brut"], para)
        _vergi(ln, s["matrah"], s["kdv_tutar"], s.get("kdv", 20), para)
        if s.get("tevkifat_tutar"):
            wt = _e(ln, "cac:WithholdingTaxTotal")
            _tutar(wt, "cbc:TaxAmount", s["tevkifat_tutar"], para)
            _tevkifat_alt(wt, s["tevkifat_kod"], s["kdv_tutar"], s["tevkifat_tutar"], para)
        _e(_e(ln, "cac:Item"), "cbc:Name", s.get("ad", ""))
        pr = _e(ln, "cac:Price")
        _e(pr, "cbc:PriceAmount", f"{d(s.get('birim_fiyat', 0)).normalize():f}", currencyID=para)

    ET.indent(inv)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(inv, encoding="unicode")


# ---------------------------------------------------------------- Gelen fatura okuma
def _bul(root, yol):
    el = root
    for parca in yol.split("/"):
        if el is None:
            return None
        el = next((c for c in el if c.tag.split("}")[-1] == parca), None)
    return el


def _metin(root, yol):
    el = _bul(root, yol)
    return el.text.strip() if el is not None and el.text else ""


def xml_ozet(xml_metni):
    """Gelen bir UBL faturadan liste için gereken alanları çıkarır."""
    root = guvenli_xml(xml_metni.encode("utf-8") if isinstance(xml_metni, str) else xml_metni)
    p = _bul(root, "AccountingSupplierParty/Party")
    unvan = _metin(p, "PartyName/Name") if p is not None else ""
    if not unvan and p is not None:
        unvan = (_metin(p, "Person/FirstName") + " " + _metin(p, "Person/FamilyName")).strip()
    vkn = _metin(p, "PartyIdentification/ID") if p is not None else ""
    tutar_el = _bul(root, "LegalMonetaryTotal/PayableAmount")
    irs = [_metin(c, "ID") for c in root if c.tag.endswith("DespatchDocumentReference")]
    for c in root:
        if c.tag.endswith("Note") and c.text:
            irs += re.findall(r"[İI]rsaliye\s*(?:No|Numaras[ıi])?\s*[:.]?\s*([A-Z0-9][A-Z0-9\-/]{3,})", c.text, re.I)
    taraf = {}
    if p is not None:
        taraf = {"unvan": unvan, "vkn": vkn, "vergi_dairesi": _metin(p, "PartyTaxScheme/TaxScheme/Name"),
                 "adres": _metin(p, "PostalAddress/StreetName"), "ilce": _metin(p, "PostalAddress/CitySubdivisionName"),
                 "il": _metin(p, "PostalAddress/CityName"), "telefon": _metin(p, "Contact/Telephone"),
                 "eposta": _metin(p, "Contact/ElectronicMail")}
    matrah = _metin(root, "LegalMonetaryTotal/TaxExclusiveAmount")
    kdv = _metin(root, "TaxTotal/TaxAmount")
    tev = _metin(root, "WithholdingTaxTotal/TaxAmount")
    kur = _metin(root, "PricingExchangeRate/CalculationRate")

    def sayi(x):
        try:
            return float(x or 0)
        except ValueError:
            return 0.0
    tarih = _metin(root, "IssueDate")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", tarih):
        raise ValueError(f"Fatura tarihi geçersiz: {tarih[:20]!r}")
    para_birimi = tutar_el.get("currencyID", "TRY") if tutar_el is not None else "TRY"
    vade = _metin(root, "PaymentMeans/PaymentDueDate") or _metin(root, "PaymentTerms/PaymentDueDate")
    return {
        "vade_tarihi": vade if re.match(r"^\d{4}-\d{2}-\d{2}$", vade) else None,
        "tevkifat_toplam": sayi(tev), "kur": sayi(kur) or 1.0,
        "irsaliye_nolar": sorted({re.sub(r"[^A-Z0-9\-/]", "", i.strip().upper())[:40] for i in irs if i and i.strip()}),
        "taraf": taraf, "matrah": sayi(matrah), "kdv_toplam": sayi(kdv),
        "tip": _metin(root, "InvoiceTypeCode"),
        "uuid": _metin(root, "UUID")[:64],
        "fatura_no": re.sub(r"[^A-Za-z0-9\-/]", "", _metin(root, "ID"))[:40],
        "tarih": tarih,
        "gonderen_unvan": unvan[:250],
        "gonderen_vkn": re.sub(r"\D", "", vkn)[:11],
        "tutar": sayi(tutar_el.text if tutar_el is not None else 0),
        "para_birimi": para_birimi if re.match(r"^[A-Z]{3}$", para_birimi) else "TRY",
    }


def xml_satirlar(xml_metni):
    """Görüntüleme için gelen faturanın satırlarını ve taraflarını çıkarır."""
    root = guvenli_xml(xml_metni.encode("utf-8"))
    satirlar = []
    for ln in (c for c in root if c.tag.endswith("InvoiceLine")):
        q = _bul(ln, "InvoicedQuantity")
        satirlar.append({
            "ad": _metin(ln, "Item/Name"),
            "miktar": q.text if q is not None else "",
            "birim": BIRIMLER.get(q.get("unitCode", ""), q.get("unitCode", "")) if q is not None else "",
            "birim_fiyat": _metin(ln, "Price/PriceAmount"),
            "kdv": _metin(ln, "TaxTotal/TaxSubtotal/Percent"),
            "tutar": _metin(ln, "LineExtensionAmount"),
        })
    return satirlar
