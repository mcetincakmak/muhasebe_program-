"""1.x (tek firma, tek şifre) kurulumundan 2.x'e geçiş."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap


def test_eski_surum_tasinir():
    veri = tempfile.mkdtemp()
    sys.path.insert(0, os.getcwd())
    # 1.x benzeri veritabanı: ayarlar tablosunda şifre ve QNB ayarları, bir cari
    con = sqlite3.connect(os.path.join(veri, "fatura.db"))
    con.executescript("""
        CREATE TABLE ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);
        CREATE TABLE cariler (id INTEGER PRIMARY KEY AUTOINCREMENT, unvan TEXT NOT NULL, vkn TEXT);
        CREATE TABLE oturumlar (token TEXT PRIMARY KEY, olusturma TEXT);
        INSERT INTO cariler(unvan, vkn) VALUES ('Eski Müşteri', '1234567890');""")
    from app.core.guvenlik import sifre_hash
    con.executemany("INSERT INTO ayarlar VALUES (?,?)", [
        ("sifre_hash", sifre_hash("eskisifre")), ("firma_unvan", "Eski Firma"), ("qnb_mod", "test"),
        ("qnb_kullanici", "kullanici1"), ("qnb_sifre", "s3cret")])
    con.commit()
    con.close()
    os.makedirs(os.path.join(veri, "belgeler"))
    open(os.path.join(veri, "belgeler", "a.jpg"), "wb").write(b"x")
    kod = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app)
        assert c.get("/api/durum").json()["kurulum_gerekli"] is False
        r = c.post("/api/giris", json={"kullanici_adi": "yonetici", "sifre": "eskisifre"})
        assert r.status_code == 200, r.text
        ben = c.get("/api/ben").json()
        assert ben["firma"]["unvan"] == "Eski Firma" and ben["mod"] == "test"
        assert c.get("/api/cariler").json()[0]["unvan"] == "Eski Müşteri"
        a = c.get("/api/ayarlar").json()
        assert a["entegrator"] == "qnb" and a["ent_kullanici"] == "kullanici1" and a["ent_sifre_var"]
        assert c.get("/belge/a.jpg").status_code == 200
        print("GECIS_TAMAM")
    """)
    ortam = dict(os.environ, FATURA_VERI=veri, FATURA_ZAMANLAYICI="0")
    r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, env=ortam, cwd=os.getcwd())
    assert "GECIS_TAMAM" in r.stdout, r.stdout + r.stderr
    assert os.path.exists(os.path.join(veri, "eski_surum_fatura.db"))
