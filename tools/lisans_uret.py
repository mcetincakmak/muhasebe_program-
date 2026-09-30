"""Müşteriye lisans anahtarı üretir. BU DOSYA VE ÖZEL ANAHTAR MÜŞTERİYE VERİLMEZ.

Kullanım:
  python tools/lisans_uret.py --anahtar lisans_ozel_anahtar.pem --musteri "Göl Yapı A.Ş." \
      --bitis 2027-12-31 --firma 1 --kullanici 3 [--makine ABCD-1234-...]
Makine kodu, müşterinin programında Yönetim > Lisans sayfasında görünür.
"""
import argparse
import base64
import json
import uuid

from cryptography.hazmat.primitives import serialization


def b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--anahtar", required=True)
    p.add_argument("--musteri", required=True)
    p.add_argument("--bitis", required=True, help="YYYY-AA-GG")
    p.add_argument("--firma", type=int, default=1)
    p.add_argument("--kullanici", type=int, default=3)
    p.add_argument("--makine", default="")
    a = p.parse_args()
    ozel = serialization.load_pem_private_key(open(a.anahtar, "rb").read(), password=None)
    govde = b64(json.dumps({"no": uuid.uuid4().hex[:10].upper(), "musteri": a.musteri, "bitis": a.bitis,
                            "firma": a.firma, "kullanici": a.kullanici, "makine": a.makine},
                           ensure_ascii=False, separators=(",", ":")).encode())
    print(govde + "." + b64(ozel.sign(govde.encode())))


if __name__ == "__main__":
    main()
