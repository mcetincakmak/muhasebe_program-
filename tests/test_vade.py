"""Vade takibi: vade tarihinin belirlenmesi, FIFO ile açık kalemler, gecikme ve yaşlandırma."""
import os
import tempfile
from datetime import date, timedelta

import pytest

os.environ.setdefault("FATURA_VERI", tempfile.mkdtemp())
os.environ["FATURA_ZAMANLAYICI"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.core import db  # noqa: E402
from app.main import app  # noqa: E402
from app.api.vade import acik_kalemler  # noqa: E402
from app.servisler.ubl import fatura_xml, xml_ozet  # noqa: E402


def gun(n):
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture(scope="module")
def c():
    from app.core import guvenlik
    guvenlik.GIRIS_DENEMELERI.clear()  # aynı oturumda çalışan kilit testi yöneticiyi kilitlemiş olabilir
    t = TestClient(app)
    if t.post("/api/giris", json={"kullanici_adi": "yonetici", "sifre": "gizli1234"}).status_code != 200:
        r = t.post("/api/kurulum", json={"kullanici_adi": "yonetici", "sifre": "gizli1234", "firma_unvan": "Vade Ltd."})
        assert r.status_code == 200, r.text
    t.put("/api/ayarlar", json={"firma_unvan": "Vade Ltd.", "firma_vkn": "4810012345",
                                "firma_vergi_dairesi": "Burdur", "firma_il": "Burdur"})
    return t


def _satis(c, cari_id, tutar, tarih, vade=""):
    f = c.post("/api/faturalar", json={"cari_id": cari_id, "tarih": tarih, "vade_tarihi": vade,
                                       "satirlar": [{"ad": "Hizmet", "miktar": 1, "birim_fiyat": tutar, "kdv": 0}]})
    assert f.status_code == 200, f.text
    g = c.post(f"/api/faturalar/{f.json()['id']}/gonder")
    assert g.status_code == 200, g.text
    return g.json()


def test_vade_xml_yazilir_ve_okunur():
    x = fatura_xml({"fatura_no": "ABC2026000000009", "uuid": "u-v", "tip": "EFATURA", "tarih": "2026-09-01",
                    "vade_tarihi": "2026-10-01", "satirlar": [{"ad": "a", "miktar": 1, "birim_fiyat": 10, "kdv": 20}]},
                   {"unvan": "S", "vkn": "1234567890"}, {"unvan": "A", "vkn": "1111111111"})
    assert "<cbc:PaymentDueDate>2026-10-01</cbc:PaymentDueDate>" in x
    assert xml_ozet(x)["vade_tarihi"] == "2026-10-01"
    x2 = fatura_xml({"fatura_no": "ABC2026000000010", "uuid": "u-w", "tip": "EFATURA", "tarih": "2026-09-01",
                     "satirlar": [{"ad": "a", "miktar": 1, "birim_fiyat": 10, "kdv": 20}]},
                    {"unvan": "S", "vkn": "1234567890"}, {"unvan": "A", "vkn": "1111111111"})
    assert "PaymentMeans" not in x2 and xml_ozet(x2)["vade_tarihi"] is None


def test_cari_vade_gunu_dogrulanir(c):
    assert c.post("/api/cariler", json={"unvan": "Hatalı", "vade_gun": "abc"}).status_code == 400
    assert c.post("/api/cariler", json={"unvan": "Hatalı", "vade_gun": 400}).status_code == 400
    k = c.post("/api/cariler", json={"unvan": "Vadeli Müşteri", "vkn": "1212121212", "vade_gun": 30}).json()
    assert k["vade_gun"] == 30


def test_vade_carinin_gununden_hesaplanir_ve_elle_girilebilir(c):
    cari = c.post("/api/cariler", json={"unvan": "Otuz Gün A.Ş.", "vkn": "1313131313", "vade_gun": 30}).json()
    f = c.post("/api/faturalar", json={"cari_id": cari["id"], "tarih": "2026-09-01",
                                       "satirlar": [{"ad": "x", "miktar": 1, "birim_fiyat": 10}]}).json()
    assert f["vade_tarihi"] == "2026-10-01"
    f = c.post("/api/faturalar", json={"cari_id": cari["id"], "tarih": "2026-09-01", "vade_tarihi": "2026-09-15",
                                       "satirlar": [{"ad": "x", "miktar": 1, "birim_fiyat": 10}]}).json()
    assert f["vade_tarihi"] == "2026-09-15"
    r = c.post("/api/faturalar", json={"cari_id": cari["id"], "tarih": "2026-09-01", "vade_tarihi": "2026-08-01",
                                       "satirlar": [{"ad": "x", "miktar": 1, "birim_fiyat": 10}]})
    assert r.status_code == 400
    # peşin cari: vade boş kalır
    pesin = c.post("/api/cariler", json={"unvan": "Peşin Ltd.", "vkn": "1414141414"}).json()
    f = c.post("/api/faturalar", json={"cari_id": pesin["id"], "tarih": "2026-09-01",
                                       "satirlar": [{"ad": "x", "miktar": 1, "birim_fiyat": 10}]}).json()
    assert f["vade_tarihi"] is None


def test_fifo_kismi_tahsilat_ve_gecikme(c):
    cari = c.post("/api/cariler", json={"unvan": "FIFO Ticaret", "vkn": "1515151515"}).json()
    eski = _satis(c, cari["id"], 1000, gun(-70), gun(-40))   # 40 gün gecikmiş
    yeni = _satis(c, cari["id"], 500, gun(-5), gun(10))      # vadesi gelmedi
    kasa = c.get("/api/hesaplar").json()[0]
    c.post("/api/hareketler", json={"tur": "TAHSILAT", "cari_id": cari["id"], "hesap_id": kasa["id"],
                                    "tarih": gun(-1), "tutar": 600})
    r = c.get(f"/api/vade?cari_id={cari['id']}").json()
    acik = {x["kaynak_id"]: x for x in r["alacaklar"]}
    # Tahsilat önce en eski faturayı kapatır: eski faturadan 400, yeni faturanın tamamı açık
    assert acik[eski["id"]]["acik"] == 400 and acik[eski["id"]]["gecikme"] == 40 and acik[eski["id"]]["grup"] == "31-60"
    assert acik[yeni["id"]]["acik"] == 500 and acik[yeni["id"]]["grup"] == "gelmedi"
    assert r["ozet"]["alacak"]["toplam"] == 900 == c.get(f"/api/cariler/{cari['id']}").json()["bakiye"]
    assert r["ozet"]["alacak"]["vadesi_gecen"] == 400 and r["ozet"]["alacak"]["vadesi_gecen_adet"] == 1
    assert r["borclar"] == []
    # kalanı da ödenince açık kalem kalmaz
    c.post("/api/hareketler", json={"tur": "TAHSILAT", "cari_id": cari["id"], "hesap_id": kasa["id"],
                                    "tarih": gun(0), "tutar": 900})
    assert c.get(f"/api/vade?cari_id={cari['id']}").json()["alacaklar"] == []


def test_alis_faturasi_borc_olarak_izlenir_ve_vade_degistirilir(c):
    ted = c.post("/api/cariler", json={"unvan": "Vadeli Tedarikçi", "vkn": "1616161616", "tur": "tedarikci",
                                       "vade_gun": 15}).json()
    g = c.post("/api/gelen", json={"cari_id": ted["id"], "fatura_no": "TED2026000000001", "tarih": gun(-20),
                                   "tutar": 250}).json()
    assert g["vade_tarihi"] == gun(-5)
    b = c.get(f"/api/vade?cari_id={ted['id']}").json()["borclar"]
    assert len(b) == 1 and b[0]["acik"] == 250 and b[0]["gecikme"] == 5
    g = c.put(f"/api/gelen/{g['id']}/vade", json={"vade_tarihi": gun(3)}).json()
    assert g["vade_tarihi"] == gun(3)
    assert c.get(f"/api/vade?cari_id={ted['id']}").json()["borclar"][0]["grup"] == "gelmedi"


def test_gonderilmis_faturanin_vadesi_degistirilebilir(c):
    cari = c.post("/api/cariler", json={"unvan": "Erteleme Ltd.", "vkn": "1717171717"}).json()
    f = _satis(c, cari["id"], 100, gun(-30), gun(-10))
    f = c.put(f"/api/faturalar/{f['id']}/vade", json={"vade_tarihi": gun(20)}).json()
    assert f["vade_tarihi"] == gun(20)
    assert c.put(f"/api/faturalar/{f['id']}/vade", json={"vade_tarihi": "2000-01-01"}).status_code == 400


def test_ozet_vadesi_gecenleri_gosterir(c):
    o = c.get("/api/ozet").json()
    assert o["vade"]["alacak"]["vadesi_gecen"] >= 0 and "gruplar" in o["vade"]["borc"]


def test_toplam_acik_alacak_bakiyelerle_tutarli(c):
    with db.firma_baglami(c.get("/api/ben").json()["firma"]["id"]):
        with db.islem() as con:
            alacaklar, borclar = acik_kalemler(con)
    bakiyeler = c.get("/api/cari-bakiyeleri").json()
    assert round(sum(x["acik"] for x in alacaklar), 2) == round(sum(v for v in bakiyeler.values() if v > 0), 2)
    assert round(sum(x["acik"] for x in borclar), 2) == round(-sum(v for v in bakiyeler.values() if v < 0), 2)


def test_eski_veritabanina_vade_gocu_uygulanir():
    from app.core import gocler
    fid = 99
    with db.firma_baglami(fid):
        pass
    yol = db.firma_db_yolu(fid)
    import sqlite3
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    con = sqlite3.connect(yol, isolation_level=None)
    con.row_factory = sqlite3.Row
    for no, _ad, fonk in gocler.FIRMA_GOCLERI[:2]:
        con.execute("BEGIN")
        fonk(con)
        con.execute(f"PRAGMA user_version = {no}")
        con.execute("COMMIT")
    con.close()
    assert gocler.firma_hazirla(fid) == 3
    con = sqlite3.connect(yol)
    assert "vade_gun" in {r[1] for r in con.execute("PRAGMA table_info(cariler)")}
    assert "vade_tarihi" in {r[1] for r in con.execute("PRAGMA table_info(gelen_faturalar)")}
    con.close()
