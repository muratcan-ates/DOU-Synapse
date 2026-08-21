"""Sorgu yolu p95'i ve uyanma süresi ölçer (T055).

## İki ayrı sayı, bilerek ayrı raporlanır

SC-010'un `< 10 sn` hedefi **yalnız sıcak replika için** geçerlidir. Uyanma
süresini p95'in içine karıştırmak, iki farklı olayı tek bir yanıltıcı sayıya
indirger (Anayasa III). Bu yüzden iki mod vardır ve çıktıları birbirine
karışmaz:

    warm  — sıcak replikada `/chat` uçtan uca gecikmesi (en az 30 istek)
    cold  — scale-to-zero'dan uyanma: ilk 200'e kadar geçen süre

## Sıcak ölçümde ne DAHİL değil

Ölçüm gerçek HTTP üzerinden yapılır (süreç içi ASGI değil): uvicorn, soket ve
serileştirme maliyeti sayıya dâhil olmalıdır.

Ama LLM anahtarı yokken üretim deterministik sahte sağlayıcıya düşer ve
generation terimi ~0 olur. O koşulda ölçülen p95 **retrieval + guardrail +
veritabanı** yoludur, üretim p95'i DEĞİLDİR. Betik bunu çıktının başında
söyler; sayıyı raporlayan kişi bu satırı da taşımak zorundadır.

## Kullanım

    uv run python scripts/measure_latency.py warm \\
        --base-url http://localhost:8023 --course-id <uuid> --user-id <uuid>

    uv run python scripts/measure_latency.py cold \\
        --base-url https://<aca-host> --repeat 5 --idle-wait 900
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx


def _percentile(values: list[float], fraction: float) -> float:
    """Doğrusal interpolasyonlu yüzdelik.

    `statistics.quantiles` n=100 ile 30 örnekte kaba basamaklar üretir; p95 gibi
    uç bir noktada bu, ölçümün kendisinden büyük bir yuvarlama hatası demek.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summarise(label: str, samples: list[float]) -> dict[str, float]:
    stats = {
        "n": len(samples),
        "min_ms": min(samples),
        "median_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "p99_ms": _percentile(samples, 0.99),
        "max_ms": max(samples),
        "mean_ms": statistics.fmean(samples),
    }
    print(f"\n{label}")
    print(f"  n         : {stats['n']}")
    print(f"  en düşük  : {stats['min_ms']:8.1f} ms")
    print(f"  medyan    : {stats['median_ms']:8.1f} ms")
    print(f"  p95       : {stats['p95_ms']:8.1f} ms")
    print(f"  p99       : {stats['p99_ms']:8.1f} ms")
    print(f"  en kötü   : {stats['max_ms']:8.1f} ms")
    return stats


def _load_questions(path: Path) -> list[str]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    questions: list[str] = []
    for entry in spec["courses"]:
        questions += entry.get("questions", [])
    return questions


async def _warm(args: argparse.Namespace) -> dict[str, object]:
    questions = _load_questions(args.questions)
    headers = {"Authorization": f"Bearer {args.token or f'dev:{args.user_id}'}"}
    url = f"/courses/{args.course_id}/chat"

    samples: list[float] = []
    miss_samples: list[float] = []
    hit_samples: list[float] = []
    rate_limited = 0

    async with httpx.AsyncClient(base_url=args.base_url, timeout=120.0) as client:
        # Isınma istekleri ölçüme GİRMEZ: ilk istek modeli ve bağlantı havuzunu
        # yükler ve sıcak replika tanımına aykırıdır.
        for index in range(args.warmup):
            await client.post(
                url,
                json={"question": questions[index % len(questions)], "mode": "qa"},
                headers=headers,
            )

        for index in range(args.count):
            question = questions[index % len(questions)]
            started = time.perf_counter()
            response = await client.post(
                url, json={"question": question, "mode": "qa"}, headers=headers
            )
            elapsed_ms = (time.perf_counter() - started) * 1000

            if response.status_code == 429:
                # Sınıra takılan istek bir gecikme ölçümü değildir; sayılmaz ama
                # gizlenmez de.
                rate_limited += 1
                await asyncio.sleep(args.rate_limit_wait)
                continue
            response.raise_for_status()
            samples.append(elapsed_ms)
            # İki yol AYRI ölçülür. Önbellek isabeti LLM'i tamamen atlar; ikisini
            # tek bir p95'te toplamak, o sayıyı önbellek isabet oranına bağlı
            # anlamsız bir ortalamaya çevirir. Üretim p95'i ıskalanan yoldur;
            # isabet eden yol ise demo günü çevrimdışı senaryonun gecikmesidir.
            (hit_samples if response.json().get("cached") else miss_samples).append(elapsed_ms)

    if not samples:
        print("hiç ölçüm alınamadı")
        return {}

    result: dict[str, object] = {"mode": "warm", "rate_limited": rate_limited}
    if miss_samples:
        result["cache_miss"] = _summarise(
            "SICAK REPLİKA — /chat, önbellek ISKALADI (üretim yolu)", miss_samples
        )
    if hit_samples:
        result["cache_hit"] = _summarise(
            "SICAK REPLİKA — /chat, önbellekten (çevrimdışı demo yolu)", hit_samples
        )
    if rate_limited:
        print(f"\nsınıra takılan (ölçüme girmedi): {rate_limited}")
    return result


async def _cold(args: argparse.Namespace) -> dict[str, object]:
    """Uyuyan replikanın ilk 200'e kadar geçen süresi."""
    samples: list[float] = []
    first_question_samples: list[float] = []

    async with httpx.AsyncClient(timeout=args.wake_timeout) as client:
        for attempt in range(args.repeat):
            if attempt and args.idle_wait:
                print(
                    f"replikanın tekrar uyuması için {args.idle_wait:.0f} sn bekleniyor…",
                    flush=True,
                )
                await asyncio.sleep(args.idle_wait)

            started = time.perf_counter()
            deadline = started + args.wake_timeout
            while time.perf_counter() < deadline:
                try:
                    response = await client.get(f"{args.base_url.rstrip('/')}/health/ready")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    # Uyuyan servis bağlantıyı reddedebilir; bu da uyanma
                    # süresinin parçasıdır.
                    pass
                await asyncio.sleep(0.25)
            else:
                print(f"deneme {attempt + 1}: {args.wake_timeout} sn içinde uyanmadı")
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            samples.append(elapsed_ms)
            print(f"deneme {attempt + 1}: hazır — {elapsed_ms / 1000:.2f} sn")

            # `/health/ready` embedding modelini YÜKLEMEZ; model ilk embed
            # çağrısında tembel yüklenir. Demo günü önemli olan "ilk sorunun ne
            # kadar sürdüğü" ve o sayı model yükleme maliyetini içerir. Uyanma
            # süresini tek başına raporlamak bu maliyeti gizlerdi.
            if args.course_id and (args.user_id or args.token):
                questions = _load_questions(args.questions)
                headers = {"Authorization": f"Bearer {args.token or f'dev:{args.user_id}'}"}
                started_chat = time.perf_counter()
                chat = await client.post(
                    f"{args.base_url.rstrip('/')}/courses/{args.course_id}/chat",
                    json={"question": questions[0], "mode": "qa"},
                    headers=headers,
                )
                first_chat_ms = (time.perf_counter() - started_chat) * 1000
                if chat.status_code == 200:
                    first_question_samples.append(first_chat_ms)
                    print(f"           ilk soru — {first_chat_ms / 1000:.2f} sn")
                else:
                    print(f"           ilk soru başarısız: HTTP {chat.status_code}")

    if not samples:
        print("hiç uyanma ölçülemedi")
        return {}

    result: dict[str, object] = {"mode": "cold"}
    result["wake"] = _summarise("SOĞUK BAŞLANGIÇ — /health/ready'ye kadar", samples)
    if first_question_samples:
        result["first_question"] = _summarise(
            "SOĞUK BAŞLANGIÇ — ilk soru (model yükleme dâhil)", first_question_samples
        )
    print("\n  Bu sayılar SC-010'un <10 sn hedefine DÂHİL DEĞİLDİR; hedef sıcak replika içindir.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["warm", "cold"])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--user-id")
    parser.add_argument("--token", help="gerçek JWT; verilmezse dev:<user-id> kullanılır")
    parser.add_argument(
        "--questions", type=Path, default=Path(__file__).with_name("demo_questions.json")
    )
    parser.add_argument("--count", type=int, default=30, help="ölçülecek istek sayısı")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--rate-limit-wait", type=float, default=61.0)
    parser.add_argument("--repeat", type=int, default=3, help="cold: kaç uyanma ölçülecek")
    parser.add_argument(
        "--idle-wait",
        type=float,
        default=0.0,
        help="cold: denemeler arası bekleme (replikanın tekrar uyuması için)",
    )
    parser.add_argument("--wake-timeout", type=float, default=180.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if args.mode == "warm" and not (args.course_id and (args.user_id or args.token)):
        parser.error("warm modu --course-id ve --user-id/--token ister")

    stats = asyncio.run(_warm(args) if args.mode == "warm" else _cold(args))

    if args.report and stats:
        args.report.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if stats else 1


if __name__ == "__main__":
    sys.exit(main())
