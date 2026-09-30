"""Entegratör kaydı. Firma ayarlarındaki "entegrator" anahtarına göre doğru eklentiyi döndürür."""
from .deneme import Deneme
from .qnb import QNB
from .temel import Entegrator, EntegratorHatasi

KAYIT = {Deneme.kod: Deneme, QNB.kod: QNB}

__all__ = ["Entegrator", "EntegratorHatasi", "KAYIT", "istemci", "liste"]


def istemci(ayarlar):
    return KAYIT.get(ayarlar.get("entegrator") or "deneme", Deneme)(ayarlar)


def liste():
    return [{"kod": s.kod, "ad": s.ad, "alanlar": s.alanlar} for s in KAYIT.values()]
