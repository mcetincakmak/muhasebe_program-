"""Program geneli yapılandırma."""
import os

SURUM = "2.0.0"
KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Veri klasörü: FATURA_VERI ortam değişkeniyle değiştirilebilir (ör. C:\ProgramData\eFatura)
VERI = os.environ.get("FATURA_VERI") or os.path.join(KOK, "veri")
