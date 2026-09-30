"""Ortak yardımcılar."""
import threading

from fastapi import HTTPException

from . import db

FIRMA_ALANLARI = ["unvan", "vkn", "vergi_dairesi", "mersis", "adres", "ilce", "il", "ulke", "telefon", "eposta"]
GONDERIM_KILIDI = threading.Lock()  # aynı anda iki gönderim aynı fatura numarasını almasın
TARAMA_KILIDI = threading.Lock()    # elle ve otomatik tarama üst üste binmesin


def hata(mesaj, kod=400):
    raise HTTPException(kod, mesaj)


def firma():
    a = db.ayarlar_hepsi()
    return {k: a.get("firma_" + k, "") for k in FIRMA_ALANLARI}
