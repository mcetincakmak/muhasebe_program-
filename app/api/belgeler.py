"""Belge fotoğrafları."""
import base64
import os
import re
import uuid as uuidlib
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..core import db
from ..core.ortak import hata

router = APIRouter()


# ------------------------------------------------------------------ belge fotoğrafları
def _fotolari_kaydet(veri_urller):
    """Tarayıcıdan gelen data:image/...;base64 listesini diske yazar. [(dosya_adi, mime, bytes)]"""
    os.makedirs(db.belge_dizini(), exist_ok=True)
    if len(veri_urller or []) > 10:
        hata("Bir belge için en fazla 10 fotoğraf yükleyebilirsiniz.")
    sonuc = []
    for u in veri_urller or []:
        m = re.match(r"^data:(image/(?:jpeg|png|webp));base64,(.+)$", u or "", re.S)
        if not m:
            hata("Fotoğraf okunamadı. JPEG veya PNG yükleyin.")
        ham = base64.b64decode(m.group(2))
        if len(ham) > 15 * 1024 * 1024:
            hata("Fotoğraf çok büyük (en fazla 15 MB).")
        uzanti = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[m.group(1)]
        ad = f"{datetime.now():%Y%m%d}-{uuidlib.uuid4().hex[:10]}.{uzanti}"
        with open(os.path.join(db.belge_dizini(), ad), "wb") as f:
            f.write(ham)
        sonuc.append((ad, m.group(1), ham))
    return sonuc


@router.get("/belge/{ad}")
def belge_dosyasi(ad: str):
    if not re.match(r"^[\w.-]+$", ad):
        hata("Geçersiz dosya.", 404)
    yol = os.path.join(db.belge_dizini(), ad)
    if not os.path.isfile(yol):
        hata("Dosya bulunamadı.", 404)
    return FileResponse(yol)


