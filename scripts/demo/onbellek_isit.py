#!/usr/bin/env python3
"""Sahne sorularının cevap önbelleğini ısıtır — kotaya bölünerek.

## Neden var

`sahne_provasi.py` 16 soruyu sorar ve önbellek sıcaksa 0 jeton harcar. Ama
önbellek anahtarı korpus revizyonunu içerir: derse tek bir belge yüklenince ya da
yeniden indekslenince 12 cevaplı sorunun HEPSİ ıskalar ve her biri gerçek modele
gider (~5 500 jeton). 15 Eylül'de tam bu oldu: 00:00'da ısıtılan önbellek,
07:39'daki `03-memory-management.md` yeniden indekslemesiyle soğudu; 16:42'deki
prova 1/12 cevap verdi ve öğrencinin günlük kotasını (50 000) bitirdi.

Bir öğrencinin günlük kotası 12 soruya yetmez (12 × ~5 500 ≈ 66 000 > 50 000).
Bu betik soruları **iki öğrenciye bölerek** sorar; önbellek `audience` bazlı
olduğu için hangi öğrenci ısıtırsa ısıtsın cevap tüm öğrencilere servis edilir.

## Kullanım

    # kuru koşu (varsayılan): hiç istek atmaz, planı ve kotaları yazar
    apps/api/.venv/bin/python scripts/demo/onbellek_isit.py

    # gerçek ısıtma: ilk 6 soru 3 numaralı hesapla, son 6 soru 4 numaralı hesapla
    apps/api/.venv/bin/python scripts/demo/onbellek_isit.py --calistir --ogrenci 3 --sorular 1-6
    apps/api/.venv/bin/python scripts/demo/onbellek_isit.py --calistir --ogrenci 4 --sorular 7-12

    # ısıtmadan sonra doğrula (0 jeton harcamalı):
    apps/api/.venv/bin/python scripts/demo/sahne_provasi.py

## Kural

Isıtmadan sonra DERSE HİÇBİR BELGE YÜKLENMEZ, yeniden indekslenmez, kaynak
politikası değiştirilmez — hepsi revizyonu değiştirir ve önbelleği soğutur.
Materyal yükleme demosu başka bir derste yapılır.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8020"
COURSE = "1adb6a23-49bf-4548-a884-a6ced158511e"
#: Demo öğrencileri: `22222222-…-000000000003` ve `…0004` ("önbellek 3/4").
OGRENCI = {n: f"22222222-2222-2222-2222-00000000000{n}" for n in (1, 2, 3, 4)}
GUNLUK_TAVAN = 50_000

#: `sahne_provasi.py` ile AYNI metinler; önbellek anahtarı soruyu birebir eşler,
#: tek karakter farkı ıska demektir. Banker's sorusu listede YOK: 14 Eylül 20:46'da
#: yeniden yüklenen deadlock notları o pasajı taşımıyor ve sistem doğru olarak
#: "kanıt yetersiz" diyor; ısıtmak ne mümkün ne de doğru.
SORULAR = [
    "Dairesel bekleme koşulu nedir?",
    "Deadlock oluşabilmesi için hangi dört koşulun sağlanması gerekir?",
    "Deadlock oluşması için gereken dört koşul nedir?",
    "Mutex ile semafor arasındaki fark nedir?",
    "Round-robin zamanlamada quantum süresinin seçimi neyi etkiler?",
    "Semafor nedir ve ne işe yarar?",
    "Context switch ne zaman gerçekleşir?",
    "Turnaround time ile waiting time arasındaki fark nedir?",
    "Süreç ile thread arasındaki temel fark nedir?",
    "fork() çağrısı ne döndürür?",
    "Context switch maliyeti neden yüksek?",
]


def kota(user_id: str) -> int:
    """Öğrencinin bugünkü jeton kullanımı (İstanbul günü), doğrudan veritabanından."""
    sql = (
        "select coalesce(sum(coalesce(charged_tokens,reserved_tokens)),0) from ai_token_reservations "
        f"where user_id='{user_id}' and created_at >= date_trunc('day', now() at time zone "
        "'Europe/Istanbul') at time zone 'Europe/Istanbul'"
    )
    out = subprocess.run(["psql", "-d", "dou_demo", "-Atc", sql], capture_output=True, text=True, check=False)
    return int(out.stdout.strip() or 0)


def sor(user_id: str, soru: str) -> tuple[str, int, float]:
    body = json.dumps({"question": soru, "mode": "qa"}).encode()
    req = urllib.request.Request(
        f"{API}/courses/{COURSE}/chat",
        data=body,
        headers={"Authorization": f"Bearer dev:{user_id}", "Content-Type": "application/json"},
    )
    basla = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=150) as yanit:
            veri = json.load(yanit)
    except urllib.error.HTTPError as hata:
        veri = json.loads(hata.read() or b"{}")
    except Exception as hata:  # noqa: BLE001 — ağ hatası da rapora girsin
        return ("AĞ-HATA: " + str(hata)[:40], 0, time.monotonic() - basla)
    durum = veri.get("status") or (veri.get("error") or {}).get("code", "?")
    return (durum, len(veri.get("citations") or []), time.monotonic() - basla)


def aralik(metin: str) -> list[int]:
    if metin == "hepsi":
        return list(range(1, len(SORULAR) + 1))
    bas, _, son = metin.partition("-")
    return list(range(int(bas), int(son or bas) + 1))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--calistir", action="store_true", help="gerçekten sor; verilmezse kuru koşu")
    p.add_argument("--ogrenci", type=int, choices=sorted(OGRENCI), default=3)
    p.add_argument("--sorular", default="hepsi", help="ör. 1-6, 7-12, hepsi")
    args = p.parse_args()

    user_id = OGRENCI[args.ogrenci]
    secilen = [(n, SORULAR[n - 1]) for n in aralik(args.sorular) if 1 <= n <= len(SORULAR)]
    once = kota(user_id)
    kalan = GUNLUK_TAVAN - once
    print(f"öğrenci {args.ogrenci} ({user_id[-4:]}) · bugün {once} jeton · kalan ≈ {kalan}")
    print(f"soru sayısı {len(secilen)} · tahmini maliyet ≈ {len(secilen) * 5500} (soru başı ~5 500)")
    if len(secilen) * 5500 > kalan:
        print("UYARI: kalan kota bu kadar soruya yetmeyebilir; aralığı küçült ya da hesabı değiştir.")
    if not args.calistir:
        print("\nkuru koşu — hiç istek atılmadı. Gerçek ısıtma için --calistir ekle.")
        for n, soru in secilen:
            print(f"  {n:2}. {soru}")
        return 0

    print()
    isabet = 0
    for n, soru in secilen:
        durum, atif, sn = sor(user_id, soru)
        # Önbellek isabeti ~0,3 sn altında döner; üstü gerçek model çağrısıdır.
        kaynak = "önbellek" if sn < 0.6 and durum == "answered" else "model" if durum == "answered" else "-"
        isabet += durum == "answered" and atif > 0
        print(f"  {n:2}. {durum:22} atıf={atif} {sn:6.2f}sn {kaynak:8} {soru[:52]}")
    sonra = kota(user_id)
    print(f"\ncevaplı {isabet}/{len(secilen)} · jeton {once} → {sonra} (fark {sonra - once})")
    return 0 if isabet == len(secilen) else 1


if __name__ == "__main__":
    sys.exit(main())
