"""Vade tarihi kuralları.

Faturada vade tarihi girilmezse carinin vade günü uygulanır (fatura tarihi + gün).
Carinin vade günü 0 ise fatura peşin sayılır ve vade tarihi boş kalır (vade = fatura tarihi).
"""
import re
from datetime import date, timedelta

from ..core.ortak import hata


def tarih_mi(t):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", t or ""):
        return False
    try:
        date.fromisoformat(t)
    except ValueError:
        return False
    return True


def vade_belirle(con, cari_id, fatura_tarihi, girilen=None):
    """Girilen vade tarihini doğrular; yoksa carinin vade gününden hesaplar. None: peşin."""
    if girilen:
        if not tarih_mi(girilen):
            hata("Vade tarihi geçersiz.")
        if fatura_tarihi and girilen < fatura_tarihi:
            hata("Vade tarihi fatura tarihinden önce olamaz.")
        return girilen
    if not cari_id or not tarih_mi(fatura_tarihi):
        return None
    r = con.execute("SELECT vade_gun FROM cariler WHERE id=?", (cari_id,)).fetchone()
    gun = int(r["vade_gun"] or 0) if r else 0
    return (date.fromisoformat(fatura_tarihi) + timedelta(days=gun)).isoformat() if gun > 0 else None
