"""Veritabanı erişimi.

Her firmanın ayrı bir SQLite dosyası vardır: <VERI>/firmalar/<id>/fatura.db
Kullanıcılar, yetkiler, oturumlar ve lisans ise ortak sistem veritabanındadır: <VERI>/sistem.db
Hangi firmanın dosyasının kullanılacağı istek başında (oturum kontrolünde) belirlenir ve
bağlam değişkeninde taşınır; iş kodu yalnızca db.islem() çağırır, firmayı bilmesi gerekmez.
"""
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

from .yapilandirma import VERI

_aktif_firma: ContextVar = ContextVar("aktif_firma", default=None)


def sistem_db_yolu():
    return os.path.join(VERI, "sistem.db")


def firma_dizini(fid=None):
    fid = fid if fid is not None else aktif_firma_id()
    return os.path.join(VERI, "firmalar", str(int(fid)))


def firma_db_yolu(fid=None):
    return os.path.join(firma_dizini(fid), "fatura.db")


def belge_dizini():
    return os.path.join(firma_dizini(), "belgeler")


def aktif_firma_id():
    fid = _aktif_firma.get()
    if fid is None:
        raise RuntimeError("Aktif firma seçilmedi.")
    return fid


@contextmanager
def firma_baglami(fid):
    """Arka plan görevleri gibi istek dışı kodda firmayı belirlemek için."""
    anahtar = _aktif_firma.set(fid)
    try:
        yield
    finally:
        _aktif_firma.reset(anahtar)


def _baglan(yol):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    con = sqlite3.connect(yol, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def baglan():
    return _baglan(firma_db_yolu())


@contextmanager
def _islem(yol):
    con = _baglan(yol)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def islem():
    """Aktif firmanın veritabanında bir işlem (commit/rollback otomatik)."""
    return _islem(firma_db_yolu())


def sistem():
    """Sistem veritabanında bir işlem."""
    return _islem(sistem_db_yolu())


# ------------------------------------------------------------------ firma ayarları
def ayar_al(anahtar, varsayilan=None):
    with islem() as con:
        r = con.execute("SELECT deger FROM ayarlar WHERE anahtar=?", (anahtar,)).fetchone()
    return r["deger"] if r else varsayilan


def ayarlar_hepsi():
    with islem() as con:
        return {r["anahtar"]: r["deger"] for r in con.execute("SELECT * FROM ayarlar")}


def ayar_yaz(sozluk):
    with islem() as con:
        for k, v in sozluk.items():
            con.execute("INSERT INTO ayarlar(anahtar, deger) VALUES(?, ?) "
                        "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger", (k, "" if v is None else str(v)))


def gunluge_yaz(mesaj):
    with islem() as con:
        con.execute("INSERT INTO gunluk(mesaj) VALUES(?)", (mesaj,))
        con.execute("DELETE FROM gunluk WHERE id NOT IN (SELECT id FROM gunluk ORDER BY id DESC LIMIT 500)")


def sonraki_numara(con, seri, yil):
    """GİB formatı: 3 karakter seri + 4 hane yıl + 9 hane sıra (ör. IYG2026000000001)."""
    r = con.execute("SELECT son FROM sayaclar WHERE seri=? AND yil=?", (seri, yil)).fetchone()
    son = (r["son"] if r else 0) + 1
    con.execute("INSERT INTO sayaclar(seri, yil, son) VALUES(?,?,?) "
                "ON CONFLICT(seri, yil) DO UPDATE SET son=excluded.son", (seri, yil, son))
    return f"{seri}{yil}{son:09d}"
