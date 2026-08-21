"""Event loop bloke süresi ve ısıtma kazancı ölçer (T207 / SC-014, FR-221).

## Neden bu betik kendi sunucusunu başlatıyor

`measure_latency.py` `--base-url` alıp dışarıda koşan bir sunucuya bağlanıyor.
Burada bu yetmiyor, çünkü ölçülen şey **ortamın kendisine bağlı**: sağlayıcının
`fastembed` olması, modelin nereden yükleneceği ve ısıtmanın açık mı kapalı mı
olduğu sayıyı doğrudan belirliyor. Bu üçünü betiğin dışında bırakmak,
raporlanan sayının hangi koşulda alındığını belirsiz bırakırdı (Anayasa III).
Bu yüzden sunucu burada, açık bir ortamla başlatılıp ölçüm bitince kapatılıyor.

## Ölçülen üç sayı

1. **Isıtma süresi** — süreç ayağa kalktıktan sonra `/health/ready`'nin
   `embedding: ok` demesine kadar geçen süre. Modelin diskten belleğe alınması.
2. **Bloke süresi (SC-014)** — bir belge işlenirken atılan `/health/live`
   yoklamalarının gecikmesi. Yoklamalar ARALIKSIZ atılıyor; aralarına bir
   bekleme konsaydı bloke süresi tam o boşluğa düşüp ölçülmeden geçebilirdi.
3. **İlk soru süresi** — ısıtma sonrası ilk `/chat` çağrısı. Isıtma kapalıyken
   aynı sayı model yükleme cezasını da içerir; ikisinin farkı FR-221'in
   kazancıdır.

## Kullanım

    uv run python scripts/measure_blocking.py --database-url <dsn> --port 8031
    uv run python scripts/measure_blocking.py --database-url <dsn> --no-warmup

Çıktı JSON'dur; rapora yazılacak sayı doğrudan buradan alınır, elle
yuvarlanmaz.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from collections.abc import Awaitable
from pathlib import Path
from uuid import uuid4

import httpx

API_ROOT = Path(__file__).resolve().parents[1]

#: Ölçüm sırasında yüklenen belge. PDF üretmek için pymupdf zaten kurulu.
PAGES = [
    "Deadlock icin dort Coffman kosulu birlikte saglanmalidir: karsilikli "
    "dislama, tut ve bekle, kesmesizlik ve dongusel bekleme.",
    "Round Robin algoritmasinda quantum sureyi belirler; kisa quantum baglam "
    "degistirme maliyetini artirir.",
    "Sayfalama sanal bellegi sabit boyutlu cerceveler halinde yonetir ve "
    "dis parcalanmayi ortadan kaldirir.",
]


def _make_pdf(pages: int) -> bytes:
    """`pages` sayfalık bir ders materyali üretir.

    Boyut parametre çünkü ölçülen şey ona ORANTILI: 3 sayfalık bir belgede
    ayrıştırma + embedding birkaç yüz milisaniye sürer ve sarmanın kazancı
    gürültünün içinde kaybolur. Gerçek ders materyali onlarca sayfadır
    (`max_upload_bytes` 20 MB); sayı o ölçekte anlam kazanır.
    """
    import pymupdf

    document = pymupdf.open()
    for index in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), f"[{index + 1}] {PAGES[index % len(PAGES)]}", fontsize=11)
    data: bytes = document.tobytes()
    document.close()
    return data


def _server_env(args: argparse.Namespace) -> dict[str, str]:
    """Sunucunun ortamı — ölçümün koşulu budur, bu yüzden burada açıkça yazılı."""
    env = dict(os.environ)
    env.update(
        {
            "ENVIRONMENT": "local",
            "DEV_AUTH_ENABLED": "true",
            "DATABASE_URL": args.database_url,
            "WORKER_DATABASE_URL": args.worker_database_url or args.database_url,
            "EMBEDDING_PROVIDER": "fastembed",
            "EMBEDDING_WARMUP_ENABLED": "true" if args.warmup else "false",
            # Modelin nereden geleceği. Verilmezse fastembed geçici dizinine
            # 2,1 GB'ı yeniden indirir; ölçülen sayı ağ hızı olurdu.
            "FASTEMBED_CACHE_PATH": args.model_cache,
            "EMBEDDING_CACHE_DIR": args.model_cache,
        }
    )
    env.pop("SUPABASE_JWT_SECRET", None)
    return env


def _create_profile(admin_dsn: str, user_id: str) -> None:
    """Ölçüm kullanıcısının profil satırını yazar.

    Dev auth jetonu bir kimlik taşır ama profil satırı yaratmaz; satır olmadan
    `app.create_course` üyelik yazarken yabancı anahtara takılıyor ve uç 409
    dönüyor. Testlerde bu işi `UserFactory` yapıyor.
    """
    import psycopg

    with psycopg.connect(admin_dsn) as conn:
        conn.execute(
            "INSERT INTO profiles (id, email, full_name) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (user_id, f"olcum-{user_id[:8]}@dogus.edu.tr", "Ölçüm Kullanıcısı"),
        )
        conn.commit()


async def _wait_alive(client: httpx.AsyncClient, azami_sn: float) -> float:
    """Süreç HTTP'ye cevap verene kadar geçen süre."""
    started = time.perf_counter()
    while time.perf_counter() - started < azami_sn:
        try:
            response = await client.get("/health/live")
        except httpx.TransportError:
            await asyncio.sleep(0.05)
            continue
        if response.status_code == 200:
            return time.perf_counter() - started
        await asyncio.sleep(0.05)
    raise TimeoutError("sunucu ayağa kalkmadı")


async def _wait_warm(client: httpx.AsyncClient, azami_sn: float) -> tuple[float, str]:
    """Isıtma bitene kadar geçen süre ve son durum."""
    started = time.perf_counter()
    durum = "bilinmiyor"
    while time.perf_counter() - started < azami_sn:
        response = await client.get("/health/ready")
        durum = str(response.json()["checks"].get("embedding"))
        if durum in {"ok", "disabled", "failed"}:
            return time.perf_counter() - started, durum
        await asyncio.sleep(0.1)
    return time.perf_counter() - started, durum


async def _probe_window(client: httpx.AsyncClient, work: Awaitable[None]) -> dict[str, float | int]:
    """`work` sürerken `/health/live` gecikmelerini ölçer.

    Yoklamalar ARALIKSIZ atılıyor. İlk yazımda aralarına 10 ms'lik bir bekleme
    konmuştu ve bloke süresi tam o boşluğa düşüp ölçülmeden geçti: `to_thread`
    sarması kaldırıldığı hâlde ölçüm temiz göründü. Boşluksuzluk, bu ölçümün
    bir şey söylemesinin ön koşulu.
    """
    gecikmeler: list[float] = []
    bitti = asyncio.Event()
    ilk_yoklama = asyncio.Event()

    async def yokla() -> None:
        while not bitti.is_set():
            basladi = time.perf_counter()
            response = await client.get("/health/live")
            gecikmeler.append((time.perf_counter() - basladi) * 1000)
            ilk_yoklama.set()
            response.raise_for_status()

    yoklama = asyncio.create_task(yokla())
    await ilk_yoklama.wait()
    try:
        await work
    finally:
        bitti.set()
        await yoklama

    sirali = sorted(gecikmeler)
    return {
        "n": len(sirali),
        "max_ms": round(sirali[-1], 1),
        "p95_ms": round(sirali[min(len(sirali) - 1, int(0.95 * (len(sirali) - 1)))], 1),
        "medyan_ms": round(sirali[len(sirali) // 2], 1),
        "100ms_ustu": sum(1 for x in sirali if x > 100),
    }


async def _measure(args: argparse.Namespace, base_url: str) -> dict[str, object]:
    user_id = str(uuid4())
    headers = {"Authorization": f"Bearer dev:{user_id}"}
    _create_profile(args.admin_database_url, user_id)

    async with httpx.AsyncClient(base_url=base_url, timeout=180.0) as client:
        alive_seconds = await _wait_alive(client, azami_sn=60.0)
        warm_seconds, warm_state = await _wait_warm(client, azami_sn=300.0)

        profile = await client.post(
            "/courses",
            json={"code": f"MEASURE{uuid4().hex[:6].upper()}", "title": "Ölçüm dersi"},
            headers=headers,
        )
        profile.raise_for_status()
        course_id = profile.json()["id"]

        # --- FR-221: ısıtma sonrası ilk soru ---------------------------------
        # Ölçüm ingestion'dan ÖNCE yapılıyor. İlk yazımda sonraydı ve yanlıştı:
        # belge işlemek modeli zaten yüklüyor, dolayısıyla "ilk soru" hiçbir
        # koşulda soğuk başlangıç cezası ödemiyordu ve ısıtmanın kazancı
        # ölçülemez hâle geliyordu.
        chat_sureleri: list[float] = []
        chat_durumlari: list[int] = []
        for index in range(2):
            basladi = time.perf_counter()
            response = await client.post(
                f"/courses/{course_id}/chat",
                json={"question": f"Deadlock kosullari nelerdir? ({index})"},
                headers=headers,
            )
            chat_sureleri.append((time.perf_counter() - basladi) * 1000)
            # Materyal henüz yüklenmedi; uç "kanıt yetersiz" diyebilir ve bu
            # ölçüm için sorun değil — ölçülen şey sorgu embedding'inin
            # maliyeti, cevabın kalitesi değil.
            chat_durumlari.append(response.status_code)

        # --- Taban gürültüsü --------------------------------------------------
        # Boştaki sunucuda aynı prob ne görüyor? Bu sayı olmadan yükleme
        # sırasındaki bir tepe noktası ingestion'a yazılamaz: makine yükü, GC
        # ve 2,1 GB model yüklendikten sonraki bellek baskısı da tepe üretir
        # (Anayasa III — ölçülmeyen bir nedene sayı bağlanmaz).
        taban = await _probe_window(client, asyncio.sleep(2.0))

        # --- SC-014: belge İŞLENİRKEN sağlık yoklaması ------------------------
        # Pencere yükleme YANITINDA değil, belge `completed` olduğunda kapanır.
        # İlk yazımda yanıtta kapatılmıştı ve yanlıştı: `BackgroundTasks` yanıt
        # gönderildikten SONRA koşuyor, yani asıl ağır iş ölçüm penceresinin
        # dışında kalıyordu.
        upload_basladi = time.perf_counter()
        upload_ms = 0.0
        document_id = ""

        async def yukle_ve_bekle() -> None:
            nonlocal upload_ms, document_id
            upload = await client.post(
                f"/courses/{course_id}/documents",
                files={"file": ("olcum.pdf", _make_pdf(args.pages), "application/pdf")},
                headers=headers,
            )
            upload_ms = (time.perf_counter() - upload_basladi) * 1000
            upload.raise_for_status()
            document_id = upload.json()["document"]["id"]
            while True:
                detay = await client.get(
                    f"/courses/{course_id}/documents/{document_id}", headers=headers
                )
                detay.raise_for_status()
                if detay.json()["status"] in {"completed", "failed"}:
                    return
                await asyncio.sleep(0.05)

        islenme = await _probe_window(client, yukle_ve_bekle())

    return {
        "isitma_acik": args.warmup,
        "sayfa": args.pages,
        "surec_ayaga_kalkma_sn": round(alive_seconds, 3),
        "isitma_sn": round(warm_seconds, 3),
        "isitma_durumu": warm_state,
        "yukleme_yaniti_ms": round(upload_ms, 1),
        "saglik_yoklamasi_bosta": taban,
        "saglik_yoklamasi_belge_islenirken": islenme,
        "ilk_soru_ms": round(chat_sureleri[0], 1),
        "ikinci_soru_ms": round(chat_sureleri[1], 1),
        "soru_durumlari": chat_durumlari,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--worker-database-url", default=None)
    parser.add_argument(
        "--admin-database-url",
        required=True,
        help="profil satırını yazmak için tablo sahibi bağlantısı (psycopg DSN)",
    )
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--pages", type=int, default=60, help="ölçüm belgesinin sayfa sayısı")
    parser.add_argument(
        "--model-cache",
        default=str(Path.home() / ".cache" / "dou-synapse" / "fastembed"),
        help="fastembed model önbelleği; yoksa 2,1 GB yeniden iner",
    )
    parser.add_argument("--no-warmup", dest="warmup", action="store_false")
    parser.set_defaults(warmup=True)
    args = parser.parse_args()

    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            str(args.port),
            "--log-level",
            "warning",
        ],
        cwd=API_ROOT,
        env=_server_env(args),
    )
    try:
        sonuc = asyncio.run(_measure(args, f"http://127.0.0.1:{args.port}"))
    finally:
        process.terminate()
        process.wait(timeout=30)

    json.dump(sonuc, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
