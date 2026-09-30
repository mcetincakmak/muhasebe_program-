"""e-Fatura / ön muhasebe programı: uygulama girişi.

Katmanlar:
  core/        yapılandırma, veritabanı (firma başına ayrı dosya), göçler, kimlik ve yetki, lisans
  entegrator/  özel entegratör eklentileri (deneme, QNB; yenisi tek dosya olarak eklenir)
  servisler/   iş kuralları: UBL-TR, OCR, eşleştirme, stok, tarama
  api/         HTTP uç noktaları (her modül bir APIRouter)

Çalıştırma: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import gorevler
from .api import (alis, ayarlar, belgeler, cari_hesap, cariler, faturalar, goruntule, irsaliyeler, ozet, raporlar,
                  sistem, stok, urunler)
from .core import gocler
from .core.guvenlik import oturum
from .entegrator import EntegratorHatasi
from .servisler.okuma import OkumaHatasi

STATIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = FastAPI(title="e-Fatura", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def guvenlik_katmani(request: Request, call_next):
    # Başka bir siteden, oturum çerezinizle istek gönderilmesini (CSRF) engelle
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
        kaynak = request.headers.get("origin") or request.headers.get("referer") or ""
        if kaynak:
            from urllib.parse import urlparse
            izinli = {request.headers.get("host", ""), request.headers.get("x-forwarded-host", "")} - {""}
            if urlparse(kaynak).netloc not in izinli:
                return JSONResponse({"detail": "İstek reddedildi (farklı kaynak)."}, status_code=403)
    yanit = await call_next(request)
    yanit.headers.setdefault("X-Content-Type-Options", "nosniff")
    yanit.headers.setdefault("X-Frame-Options", "DENY")
    yanit.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path == "/":
        yanit.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    if request.url.path.startswith(("/api/", "/goruntule/", "/belge/")):
        yanit.headers.setdefault("Cache-Control", "no-store")
    return yanit


@app.exception_handler(EntegratorHatasi)
def _entegrator_hatasi(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.exception_handler(OkumaHatasi)
def _okuma_hatasi(_, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


app.include_router(sistem.acik)
app.include_router(sistem.router)
for modul in (cariler, urunler, faturalar, alis, belgeler, irsaliyeler, ayarlar, ozet, goruntule,
              cari_hesap, stok, raporlar):
    app.include_router(modul.router, dependencies=[Depends(oturum)])

gocler.hepsini_hazirla()
if os.environ.get("FATURA_ZAMANLAYICI", "1") == "1":
    gorevler.baslat()


# ------------------------------------------------------------------ arayüz
app.mount("/static", StaticFiles(directory=STATIK), name="static")


@app.get("/")
def anasayfa():
    return FileResponse(os.path.join(STATIK, "index.html"))


@app.get("/sw.js")
def sw():
    return FileResponse(os.path.join(STATIK, "sw.js"), media_type="application/javascript")
