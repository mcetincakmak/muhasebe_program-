"""Veritabanı sürümleri (göçler).

Her değişiklik numaralı bir göç olarak eklenir; program açılışta eksik göçleri sırayla uygular.
Göçten önce veritabanının kopyası yedekler/ altına alınır. Mevcut göçler ASLA değiştirilmez;
yeni değişiklik için listenin sonuna yeni numarayla eklenir.
"""
import os
import shutil
import sqlite3
from datetime import datetime

from . import db
from .yapilandirma import VERI

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);
CREATE TABLE IF NOT EXISTS oturumlar (token TEXT PRIMARY KEY, olusturma TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS cariler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unvan TEXT NOT NULL, vkn TEXT, vergi_dairesi TEXT,
    ad TEXT, soyad TEXT,
    adres TEXT, ilce TEXT, il TEXT, ulke TEXT DEFAULT 'Türkiye',
    telefon TEXT, eposta TEXT,
    efatura_mukellefi INTEGER DEFAULT 0, posta_kutusu TEXT, mukellef_sorgu TEXT,
    notlar TEXT, olusturma TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS urunler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL, kod TEXT, birim TEXT DEFAULT 'C62',
    fiyat REAL DEFAULT 0, kdv REAL DEFAULT 20, aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS faturalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fatura_no TEXT UNIQUE, uuid TEXT, tip TEXT, senaryo TEXT,
    tarih TEXT, saat TEXT, cari_id INTEGER, cari_json TEXT, satirlar_json TEXT,
    notlar TEXT, para_birimi TEXT DEFAULT 'TRY',
    brut_toplam REAL DEFAULT 0, iskonto_toplam REAL DEFAULT 0, matrah REAL DEFAULT 0,
    kdv_toplam REAL DEFAULT 0, genel_toplam REAL DEFAULT 0,
    durum TEXT DEFAULT 'TASLAK', durum_aciklama TEXT, entegrator_id TEXT, xml TEXT,
    olusturma TEXT DEFAULT CURRENT_TIMESTAMP, guncelleme TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS gelen_faturalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE, fatura_no TEXT, gonderen_unvan TEXT, gonderen_vkn TEXT,
    tarih TEXT, tutar REAL, para_birimi TEXT, entegrator_id TEXT, xml TEXT,
    alinma TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sayaclar (seri TEXT, yil INTEGER, son INTEGER, PRIMARY KEY (seri, yil));
CREATE TABLE IF NOT EXISTS irsaliyeler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cari_id INTEGER, irsaliye_no TEXT, tarih TEXT,
    gonderen_unvan TEXT, gonderen_vkn TEXT, satirlar_json TEXT DEFAULT '[]',
    fotolar_json TEXT DEFAULT '[]', kaynak TEXT DEFAULT 'manuel', okuma_json TEXT,
    durum TEXT DEFAULT 'BEKLIYOR', gelen_fatura_id INTEGER, oneri_fatura_id INTEGER,
    eslesme_puani INTEGER, eslesme_aciklama TEXT, reddedilen_json TEXT DEFAULT '[]', notlar TEXT,
    olusturma TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hesaplar (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL, tur TEXT DEFAULT 'KASA', iban TEXT,
    acilis_bakiye REAL DEFAULT 0, aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hareketler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih TEXT NOT NULL, tur TEXT NOT NULL,
    cari_id INTEGER, hesap_id INTEGER, hedef_hesap_id INTEGER,
    tutar REAL NOT NULL, odeme_sekli TEXT, belge_no TEXT, aciklama TEXT,
    fatura_id INTEGER, gelen_fatura_id INTEGER,
    olusturma TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_hareket_cari ON hareketler(cari_id);
CREATE INDEX IF NOT EXISTS ix_hareket_hesap ON hareketler(hesap_id);
CREATE TABLE IF NOT EXISTS stok_hareketleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT, urun_id INTEGER NOT NULL, tarih TEXT NOT NULL, tur TEXT NOT NULL,
    miktar REAL NOT NULL, birim_fiyat REAL, kaynak TEXT, kaynak_id INTEGER, satir_ad TEXT, aciklama TEXT,
    olusturma TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_stok_urun ON stok_hareketleri(urun_id);
CREATE INDEX IF NOT EXISTS ix_stok_kaynak ON stok_hareketleri(kaynak, kaynak_id);
CREATE TABLE IF NOT EXISTS urun_eslesme (cari_id INTEGER, anahtar TEXT, urun_id INTEGER, PRIMARY KEY (cari_id, anahtar));
CREATE TABLE IF NOT EXISTS gunluk (id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT DEFAULT CURRENT_TIMESTAMP, mesaj TEXT);
"""

KOLONLAR_V1 = {
    "cariler": {
        "tur": "TEXT DEFAULT 'musteri'"
    },
    "urunler": {
        "stok_takibi": "INTEGER DEFAULT 1",
        "kritik": "REAL DEFAULT 0",
        "alis_fiyat": "REAL"
    },
    "faturalar": {
        "fatura_turu": "TEXT DEFAULT 'SATIS'",
        "iade_ref_json": "TEXT",
        "irsaliye_json": "TEXT",
        "kur": "REAL DEFAULT 1",
        "tevkifat_toplam": "REAL DEFAULT 0"
    },
    "gelen_faturalar": {
        "cari_id": "INTEGER",
        "satirlar_json": "TEXT",
        "irsaliye_nolar": "TEXT DEFAULT '[]'",
        "kaynak": "TEXT DEFAULT 'efatura'",
        "matrah": "REAL",
        "kdv_toplam": "REAL",
        "fotolar_json": "TEXT DEFAULT '[]'",
        "notlar": "TEXT",
        "tip": "TEXT DEFAULT 'SATIS'",
        "kur": "REAL DEFAULT 1",
        "tevkifat_toplam": "REAL DEFAULT 0"
    }
}


def _betik(con, sql):
    """executescript örtük COMMIT yaptığı için göçü bölmesin diye ifadeleri tek tek çalıştırır."""
    parca = ""
    for satir in sql.splitlines(keepends=True):
        parca += satir
        if sqlite3.complete_statement(parca):
            if parca.strip():
                con.execute(parca)
            parca = ""
    if parca.strip():
        con.execute(parca)


def _f1_ilk_sema(con):
    _betik(con, SCHEMA_V1)
    for tablo, kolonlar in KOLONLAR_V1.items():
        mevcut = {r["name"] for r in con.execute(f"PRAGMA table_info({tablo})")}
        for ad, tip in kolonlar.items():
            if ad not in mevcut:
                con.execute(f"ALTER TABLE {tablo} ADD COLUMN {ad} {tip}")
    if not con.execute("SELECT 1 FROM hesaplar").fetchone():
        con.execute("INSERT INTO hesaplar(ad, tur) VALUES('Nakit kasa', 'KASA')")


def _f2_entegrator_ayarlari(con):
    """Tek entegratörlü (qnb_*) ayarları genel entegratör ayarlarına çevirir; giriş şifresini firmadan kaldırır."""
    a = {r["anahtar"]: r["deger"] for r in con.execute("SELECT * FROM ayarlar")}
    mod = a.get("qnb_mod") or "deneme"
    yeni = {"entegrator": "deneme" if mod == "deneme" else "qnb", "ent_ortam": "canli" if mod == "canli" else "test"}
    if a.get("qnb_kullanici"):
        yeni["ent_kullanici"] = a["qnb_kullanici"]
    if a.get("qnb_sifre"):
        yeni["ent_sifre"] = a["qnb_sifre"]
    for k, v in yeni.items():
        con.execute("INSERT INTO ayarlar(anahtar, deger) VALUES(?,?) "
                    "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger", (k, v))
    con.execute("DELETE FROM ayarlar WHERE anahtar IN ('qnb_mod','qnb_kullanici','qnb_sifre','sifre_hash')")
    con.execute("DROP TABLE IF EXISTS oturumlar")


def _f3_vade(con):
    """Vade takibi: carinin varsayılan vade günü, satış ve alış faturalarında vade tarihi."""
    con.execute("ALTER TABLE cariler ADD COLUMN vade_gun INTEGER DEFAULT 0")
    con.execute("ALTER TABLE faturalar ADD COLUMN vade_tarihi TEXT")
    con.execute("ALTER TABLE gelen_faturalar ADD COLUMN vade_tarihi TEXT")


FIRMA_GOCLERI = [
    (1, "İlk şema", _f1_ilk_sema),
    (2, "Entegratör ayarları genelleştirildi", _f2_entegrator_ayarlari),
    (3, "Vade takibi", _f3_vade),
]


def _s1_sistem(con):
    _betik(con, """
    CREATE TABLE IF NOT EXISTS ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);
    CREATE TABLE IF NOT EXISTS firmalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT, unvan TEXT NOT NULL, aktif INTEGER DEFAULT 1,
        olusturma TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS kullanicilar (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici_adi TEXT NOT NULL UNIQUE COLLATE NOCASE, ad TEXT,
        sifre_hash TEXT NOT NULL, sistem_yoneticisi INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1,
        son_giris TEXT, olusturma TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS firma_yetkileri (
        kullanici_id INTEGER NOT NULL REFERENCES kullanicilar(id) ON DELETE CASCADE,
        firma_id INTEGER NOT NULL REFERENCES firmalar(id) ON DELETE CASCADE,
        rol TEXT NOT NULL, PRIMARY KEY (kullanici_id, firma_id));
    CREATE TABLE IF NOT EXISTS oturumlar (
        token TEXT PRIMARY KEY, kullanici_id INTEGER NOT NULL REFERENCES kullanicilar(id) ON DELETE CASCADE,
        firma_id INTEGER, olusturma TEXT DEFAULT CURRENT_TIMESTAMP);
    """)


SISTEM_GOCLERI = [
    (1, "Kullanıcılar, firmalar, yetkiler", _s1_sistem),
]


def _uygula(yol, gocler, yedek_dizini):
    con = sqlite3.connect(yol, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode = WAL")
        surum = con.execute("PRAGMA user_version").fetchone()[0]
        bekleyen = [g for g in gocler if g[0] > surum]
        if not bekleyen:
            return surum
        if con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
            os.makedirs(yedek_dizini, exist_ok=True)
            hedef = sqlite3.connect(os.path.join(yedek_dizini, f"goc_oncesi_v{surum}_{datetime.now():%Y%m%d_%H%M%S}.db"))
            con.backup(hedef)
            hedef.close()
        for no, _ad, fonk in bekleyen:
            con.execute("BEGIN")
            try:
                fonk(con)
                con.execute(f"PRAGMA user_version = {int(no)}")
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
        return bekleyen[-1][0]
    finally:
        con.close()


def firma_hazirla(fid):
    yol = db.firma_db_yolu(fid)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    return _uygula(yol, FIRMA_GOCLERI, os.path.join(db.firma_dizini(fid), "yedekler"))


def sistem_hazirla():
    os.makedirs(VERI, exist_ok=True)
    return _uygula(db.sistem_db_yolu(), SISTEM_GOCLERI, os.path.join(VERI, "yedekler"))


def eski_surumden_tasi():
    """1.x (tek firma, tek şifre) kurulumunu firma 1'e ve 'yonetici' kullanıcısına taşır."""
    eski_db = os.path.join(VERI, "fatura.db")
    if not os.path.isfile(eski_db) or os.path.isfile(db.sistem_db_yolu()):
        return None
    hedef_dizin = db.firma_dizini(1)
    os.makedirs(hedef_dizin, exist_ok=True)
    kaynak = sqlite3.connect(eski_db)
    kaynak.row_factory = sqlite3.Row
    try:
        a = {r["anahtar"]: r["deger"] for r in kaynak.execute("SELECT * FROM ayarlar")}
    except sqlite3.OperationalError:
        a = {}
    hedef = sqlite3.connect(db.firma_db_yolu(1))
    kaynak.backup(hedef)
    hedef.close()
    kaynak.close()
    if os.path.isdir(os.path.join(VERI, "belgeler")):
        shutil.move(os.path.join(VERI, "belgeler"), os.path.join(hedef_dizin, "belgeler"))
    for ek in ("", "-wal", "-shm"):
        if os.path.isfile(eski_db + ek):
            os.replace(eski_db + ek, os.path.join(VERI, f"eski_surum_fatura.db{ek}"))
    sistem_hazirla()
    with db.sistem() as con:
        con.execute("INSERT INTO firmalar(id, unvan) VALUES(1, ?)", (a.get("firma_unvan") or "Firmam",))
        if a.get("sifre_hash"):
            con.execute("INSERT INTO kullanicilar(id, kullanici_adi, ad, sifre_hash, sistem_yoneticisi) VALUES(1,?,?,?,1)",
                        ("yonetici", "Yönetici", a["sifre_hash"]))
            con.execute("INSERT INTO firma_yetkileri(kullanici_id, firma_id, rol) VALUES(1, 1, 'yonetici')")
    firma_hazirla(1)
    return 1


def hepsini_hazirla():
    eski_surumden_tasi()
    sistem_hazirla()
    with db.sistem() as con:
        firmalar = [r["id"] for r in con.execute("SELECT id FROM firmalar")]
    for fid in firmalar:
        firma_hazirla(fid)
    return firmalar
