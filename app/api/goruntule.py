"""Yazdırılabilir fatura görünümleri."""
import html
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..core import db
from ..core.ortak import firma, hata
from ..servisler.ubl import (BIRIMLER, TEVKIFAT_KODLARI, xml_satirlar)

from .faturalar import _fatura_getir

router = APIRouter()


# ------------------------------------------------------------------ yazdırılabilir görünüm
def _para(x):
    s = f"{float(x or 0):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _gorunum(baslik, no, tarih, tip, satici, alici, satirlar_html, toplamlar, notlar, durum="", para="TL"):
    e = lambda x: html.escape(str(x or ""))
    def taraf(t):
        return (f"<strong>{e(t.get('unvan'))}</strong><br>{e(t.get('adres'))}<br>"
                f"{e(t.get('ilce'))} / {e(t.get('il'))}<br>"
                f"{'Vergi dairesi: ' + e(t.get('vergi_dairesi')) + '<br>' if t.get('vergi_dairesi') else ''}"
                f"{'TCKN' if len(str(t.get('vkn') or '')) == 11 else 'VKN'}: {e(t.get('vkn'))}")
    top = "".join(f"<tr><td>{e(k)}</td><td>{_para(v)} {e(para)}</td></tr>" if isinstance(v, (int, float))
                  else f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in toplamlar)
    return HTMLResponse(f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(no)}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;color:#1d2521;max-width:820px;margin:24px auto;padding:0 16px}}
header{{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap;border-bottom:2px solid #1d2521;padding-bottom:12px}}
h1{{font-size:22px;margin:0}} .kutu{{margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:24px}}
table{{width:100%;border-collapse:collapse;margin-top:20px}} th,td{{padding:6px 8px;border-bottom:1px solid #d6ddd9;text-align:left}}
td.s,th.s{{text-align:right;font-variant-numeric:tabular-nums}} .top{{width:320px;margin-left:auto}}
.top td:last-child{{text-align:right;font-variant-numeric:tabular-nums}} .top tr:last-child td{{font-weight:700;border-top:2px solid #1d2521}}
.not{{margin-top:16px;color:#4a5550}} .etiket{{color:#5c6862;font-size:12px}}
@media print{{.yazdir{{display:none}}}} @media (max-width:600px){{.kutu{{grid-template-columns:1fr}}}}
</style></head><body>
<p class="yazdir"><button onclick="print()">Yazdır / PDF kaydet</button> {e(durum)}</p>
<header><div><h1>{e(baslik)}</h1><div class="etiket">{e(tip)}</div></div>
<div>Fatura no: <strong>{e(no) or 'Taslak'}</strong><br>Tarih: {e(tarih)}</div></header>
<div class="kutu"><div><div class="etiket">Satıcı</div>{taraf(satici)}</div><div><div class="etiket">Alıcı</div>{taraf(alici)}</div></div>
<table><thead><tr><th>Açıklama</th><th class="s">Miktar</th><th class="s">Birim fiyat</th><th class="s">KDV</th><th class="s">Tutar</th></tr></thead>
<tbody>{satirlar_html}</tbody></table>
<table class="top">{top}</table>{f'<p class="not">{e(notlar)}</p>' if notlar else ''}
<p class="not etiket">Bu sayfa bilgi amaçlı görünümdür; resmi belge entegratör/GİB kayıtlarındaki e-faturadır.</p>
</body></html>""")


@router.get("/goruntule/fatura/{fid}")
def fatura_goruntule(fid: int):
    with db.islem() as con:
        f = _fatura_getir(con, fid)
    e = lambda x: html.escape(str(x or ""))
    satirlar = "".join(
        f"<tr><td>{e(s.get('ad'))}{' (%' + e(s.get('iskonto')) + ' iskonto)' if s.get('iskonto_tutar') else ''}</td>"
        f"<td class='s'>{e(s.get('miktar'))} {e(BIRIMLER.get(s.get('birim'), s.get('birim')))}</td>"
        f"<td class='s'>{_para(s.get('birim_fiyat'))}</td><td class='s'>%{e(s.get('kdv'))}</td>"
        f"<td class='s'>{_para(s.get('matrah'))}</td></tr>" for s in f["satirlar"])
    toplamlar = [("Mal/hizmet toplamı", f["brut_toplam"])]
    if f["iskonto_toplam"]:
        toplamlar.append(("İskonto", f["iskonto_toplam"]))
    toplamlar += [("KDV matrahı", f["matrah"]), ("KDV", f["kdv_toplam"])]
    if f.get("tevkifat_toplam"):
        kodlar = sorted({s["tevkifat_kod"] for s in f["satirlar"] if s.get("tevkifat_kod")})
        toplamlar.append(("Vergiler dahil toplam", f["matrah"] + f["kdv_toplam"]))
        toplamlar.append((f"Tevkif edilen KDV ({', '.join(k + ' – ' + str(TEVKIFAT_KODLARI[k][1]) + '/10' for k in kodlar)})",
                          -f["tevkifat_toplam"]))
    toplamlar.append(("Ödenecek tutar", f["genel_toplam"]))
    para = f.get("para_birimi") or "TRY"
    if para != "TRY":
        toplamlar.append((f"TL karşılığı (kur {f['kur']:g})", f"{_para(f['genel_toplam'] * f['kur'])} TL"))
    tip = {"EFATURA": "e-Fatura", "EARSIV": "e-Arşiv fatura"}.get(f["tip"], "")
    iade = f["fatura_turu"] == "IADE"
    if iade:
        tip += " – iade edilen: " + ", ".join(f"{r['no']} ({r['tarih']})" for r in f["iade_ref"])
    return _gorunum("İade faturası" if iade else "Fatura", f["fatura_no"], f["tarih"], tip, firma(), f["cari"], satirlar, toplamlar,
                    f["notlar"], "Taslak – henüz gönderilmedi" if f["durum"] == "TASLAK" else "",
                    "TL" if para == "TRY" else para)


@router.get("/goruntule/gelen/{gid}")
def gelen_goruntule(gid: int):
    with db.islem() as con:
        r = con.execute("SELECT * FROM gelen_faturalar WHERE id=?", (gid,)).fetchone()
    if not r:
        hata("Fatura bulunamadı.", 404)
    e = lambda x: html.escape(str(x or ""))
    kalemler = xml_satirlar(r["xml"]) if r["xml"] else json.loads(r["satirlar_json"] or "[]")
    satirlar = "".join(
        f"<tr><td>{e(s.get('ad'))}</td><td class='s'>{e(s.get('miktar'))} {e(s.get('birim'))}</td>"
        f"<td class='s'>{_para(s.get('birim_fiyat') or 0)}</td><td class='s'>%{e(s.get('kdv') or '')}</td>"
        f"<td class='s'>{_para(s.get('tutar') or 0)}</td></tr>" for s in kalemler)
    return _gorunum("Alış faturası", r["fatura_no"], r["tarih"], "e-Fatura",
                    {"unvan": r["gonderen_unvan"], "vkn": r["gonderen_vkn"]}, firma(), satirlar,
                    [("Ödenecek tutar", r["tutar"])], "")


