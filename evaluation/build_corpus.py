#!/usr/bin/env python3
"""Ölçüm korpusunu sıfırdan kurar — `evaluate.py`'ın üzerinde koştuğu zemin.

Neden ayrı bir betik: eval koşusunun geçerliliği korpusun NASIL kurulduğuna bağlı.
"Hangi dosyalar yüklendi, hangi embedding sağlayıcısıyla, kaç chunk oluştu" soruları
sonradan hatırlanacak şeyler değil; her koşu dosyasına yazılması gereken meta veri.
Bu betik korpusu kurar ve aynı bilgiyi bir özet olarak basar.

Korpus, ÜRETİM YOLUNDAN geçerek kurulur: gerçek yükleme ucu, gerçek doğrulama,
gerçek worker, gerçek chunking ve embedding. Doğrudan INSERT ile kurulan bir korpus
üzerinde ölçülen Recall, üretimin gerçekten ürettiği chunk'lar hakkında hiçbir şey
söylemezdi.

`EMBEDDING_PROVIDER` bir INGEST-ZAMANI kararıdır: değiştirmek vektör uzayını
değiştirir ve tüm korpusun yeniden işlenmesini gerektirir. Yerel varsayılan
`hashing` deterministik SAHTE vektör üretir — hata vermez, yalnız sonuçlar
anlamsızdır. Ölçüm koşuları `fastembed` ile kurulmuş korpusta yapılır; betik hangi
sağlayıcıyla kurduğunu her zaman yazar ve `hashing` ise açıkça uyarır.

Kullanım (apps/api dizininden):

    uv run python ../../evaluation/build_corpus.py --database dou_synapse_eval
    EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
        --database dou_synapse_eval --recreate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from _paths import API_ROOT, DEFAULT_MATERIAL_DIR, REPO_ROOT, ensure_api_on_path

#: Korpusa giren uzantılar. `.md` DIŞARIDA: pakette her ders notunun hem `.md` hem
#: `.pdf` hâli var ve derse yüklenen PDF'tir. İkisi birden yüklenirse her sayfa iki
#: kez temsil edilir ve Recall olduğundan yüksek çıkar.
CORPUS_SUFFIXES = (".pdf", ".pptx", ".py", ".c")

INSTRUCTOR_EMAIL = "ayse.hoca@dogus.edu.tr"
COURSE_CODE = "COME301"
COURSE_TITLE = "İşletim Sistemleri"


def _psql(database: str, *args: str, pg_bin: str) -> None:
    subprocess.run(  # noqa: S603
        [f"{pg_bin}/psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", database, *args],
        check=True,
    )


def prepare_database(database: str, *, recreate: bool, pg_bin: str) -> None:
    if recreate:
        _psql("postgres", "-c", f'DROP DATABASE IF EXISTS "{database}"', pg_bin=pg_bin)
    _psql("postgres", "-c", f'CREATE DATABASE "{database}"', pg_bin=pg_bin)
    for migration in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql")):
        _psql(database, "-f", str(migration), pg_bin=pg_bin)
    _psql(database, "-f", str(REPO_ROOT / "supabase" / "local_dev_setup.sql"), pg_bin=pg_bin)
    _psql(
        database,
        "-c",
        f'GRANT CONNECT ON DATABASE "{database}" TO dou_app, dou_worker',
        pg_bin=pg_bin,
    )


async def build(material: Path, storage_root: Path, admin_dsn: str) -> dict[str, object]:
    """Dersi açar, materyali yükler, worker'ı boşaltır ve korpusu özetler."""
    ensure_api_on_path()
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app import worker
    from app.core.config import get_settings
    from app.core.db import dispose_engine, rls_session
    from app.main import create_app
    from app.modules.ingestion.storage import LocalFileStorage, set_storage

    settings = get_settings()
    set_storage(LocalFileStorage(storage_root))

    # Eğitmen profili sahip bağlantısıyla yazılır: profiles'a INSERT politikası yoktur
    # (kayıt üretimde Supabase Auth köprüsünden gelir), yani `dou_app` bu satırı
    # yazamaz — doğrusu da bu.
    instructor_id = uuid4()
    admin_engine = create_async_engine(admin_dsn)
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO profiles (id, email, full_name) VALUES (:id, :email, :name)"),
            {"id": instructor_id, "email": INSTRUCTOR_EMAIL, "name": "Ayşe Hoca"},
        )
    await admin_engine.dispose()

    headers = {"Authorization": f"Bearer dev:{instructor_id}"}
    app = create_app()
    summary: dict[str, object]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://corpus") as client:
        response = await client.post(
            "/courses", json={"code": COURSE_CODE, "title": COURSE_TITLE}, headers=headers
        )
        response.raise_for_status()
        course_id = UUID(response.json()["id"])

        uploaded: list[str] = []
        for path in sorted(material.iterdir()):
            if path.suffix.lower() not in CORPUS_SUFFIXES:
                continue
            with path.open("rb") as handle:
                response = await client.post(
                    f"/courses/{course_id}/documents",
                    files={"file": (path.name, handle.read())},
                    headers=headers,
                )
            response.raise_for_status()
            uploaded.append(path.name)

        # Yükleme ucu worker'ı arka planda tetikler ama ASGI test taşımasında arka plan
        # görevlerinin bitmesi garanti değil; kuyruk burada açıkça boşaltılır.
        while await worker.drain():
            pass
        await worker.dispose()

        documents = (await client.get(f"/courses/{course_id}/documents", headers=headers)).json()
        summary = {
            "course_id": str(course_id),
            "instructor_id": str(instructor_id),
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "uploaded": uploaded,
            "documents": [
                {
                    "file_name": document["file_name"],
                    "status": document["status"],
                    "chunk_count": document.get("chunk_count"),
                }
                for document in documents
            ],
        }
    # Konum metadata'sı gerçekten yazıldı mı: chunking'in sayfa sınırını koruduğu
    # iddiası (ARCHITECTURE §3) ancak veritabanında görülerek doğrulanır.
    #
    # Sorgu eğitmenin RLS oturumunda koşar, sahip bağlantısında değil. İlk yazışında
    # sahip bağlantısı kullanılmıştı ve sorgu boş döndü — çünkü `dou_app` bağlamsız
    # bağlanınca hiçbir satır göremez (fail-closed, Anayasa IV). Boş dönüş bir hata
    # değil, sistemin doğru davranışıydı; doğru düzeltme bağlamı kurmaktır. Böylece
    # bu sayım aynı zamanda "üye chunk'ları görebiliyor" iddiasını da doğrular.
    async with rls_session(instructor_id) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT d.file_name, count(*) AS chunks, "
                    "       count(c.page_number)  AS with_page, "
                    "       count(c.slide_number) AS with_slide, "
                    "       count(c.embedding)    AS with_embedding "
                    "FROM chunks c JOIN documents d ON d.id = c.document_id "
                    "WHERE c.course_id = :course_id GROUP BY d.file_name ORDER BY d.file_name"
                ),
                {"course_id": summary["course_id"]},
            )
        ).all()
    await dispose_engine()
    summary["chunks"] = [
        {
            "file_name": row[0],
            "chunks": row[1],
            "with_page": row[2],
            "with_slide": row[3],
            "with_embedding": row[4],
        }
        for row in rows
    ]
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ölçüm korpusunu kurar")
    parser.add_argument("--database", default="dou_synapse_eval")
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL_DIR)
    parser.add_argument("--recreate", action="store_true", help="Varsa veritabanını sil ve kur.")
    parser.add_argument("--skip-setup", action="store_true", help="Veritabanı zaten hazır.")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=API_ROOT / "storage" / "eval-corpus",
        help="Yüklenen dosyaların yerel deposu.",
    )
    parser.add_argument(
        "--pg-bin", default=os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin")
    )
    parser.add_argument(
        "--admin-dsn",
        help="Sahip/superuser bağlantısı (profiles seed'i için). Varsayılan: yerel superuser.",
    )
    parser.add_argument("--out", type=Path, help="Özeti bu dosyaya JSON olarak yaz.")
    args = parser.parse_args(argv)
    admin_dsn = args.admin_dsn or f"postgresql+psycopg://localhost/{args.database}"

    if not args.skip_setup:
        prepare_database(args.database, recreate=args.recreate, pg_bin=args.pg_bin)

    os.environ["DATABASE_URL"] = f"postgresql+psycopg://dou_app:dou_app_local@localhost/{args.database}"
    os.environ["WORKER_DATABASE_URL"] = (
        f"postgresql+psycopg://dou_worker:dou_worker_local@localhost/{args.database}"
    )
    os.environ["DEV_AUTH_ENABLED"] = "true"
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    ensure_api_on_path()
    from app.core.config import get_settings

    get_settings.cache_clear()

    summary = asyncio.run(build(args.material, args.storage_root, admin_dsn))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [d for d in summary["documents"] if d["status"] != "completed"]  # type: ignore[index]
    if failed:
        print(f"\nHATA: {len(failed)} belge 'completed' olmadı: {failed}", file=sys.stderr)
        return 1
    if summary["embedding_provider"] == "hashing":
        print(
            "\nUYARI: korpus 'hashing' sağlayıcısıyla kuruldu. Bu deterministik SAHTE "
            "bir embedding'dir; bu korpusta ölçülen Recall RAPORA GİREMEZ. Ölçüm koşusu "
            "için EMBEDDING_PROVIDER=fastembed ile yeniden kur.",
            file=sys.stderr,
        )
    print(f"\nkorpus hazır: {summary['course_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
