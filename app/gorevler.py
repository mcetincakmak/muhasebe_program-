"""Arka plan görevleri: her firmanın günlük e-fatura taraması."""
import threading
import time
from datetime import datetime

from .core import db


def _dongu():
    from .servisler.tarama import tarama_yap
    while True:
        try:
            with db.sistem() as con:
                firmalar = [r["id"] for r in con.execute("SELECT id FROM firmalar WHERE aktif=1")]
        except Exception:
            firmalar = []
        for fid in firmalar:
            with db.firma_baglami(fid):
                try:
                    saat = db.ayar_al("tarama_saati") or "09:00"
                    son = (db.ayar_al("son_otomatik_tarama") or "")[:10]
                    simdi = datetime.now()
                    if son != simdi.strftime("%Y-%m-%d") and simdi.strftime("%H:%M") >= saat:
                        db.ayar_yaz({"son_otomatik_tarama": simdi.isoformat(timespec="minutes")})
                        tarama_yap()
                except Exception as e:
                    try:
                        db.gunluge_yaz(f"Otomatik tarama hatası: {e}")
                    except Exception:
                        pass
        time.sleep(300)


def baslat():
    threading.Thread(target=_dongu, daemon=True, name="gunluk-tarama").start()
