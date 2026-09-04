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
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from _paths import API_ROOT, DEFAULT_MATERIAL_DIR, REPO_ROOT, ensure_api_on_path

#: Korpusa giren uzantılar. `.md` DIŞARIDA: pakette her ders notunun hem `.md` hem
#: `.pdf` hâli var ve derse yüklenen PDF'tir. İkisi birden yüklenirse her sayfa iki
#: kez temsil edilir ve Recall olduğundan yüksek çıkar.
CORPUS_SUFFIXES = (".pdf", ".pptx", ".py", ".c")

INSTRUCTOR_EMAIL = "ayse.hoca@dogus.edu.tr"
COURSE_CODE = "COME301"
COURSE_TITLE = "İşletim Sistemleri"


def database_identity(dsn: str) -> dict[str, object]:
    """Only non-secret connection identity may enter evidence artifacts."""
    from sqlalchemy.engine import make_url

    url = make_url(dsn)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.query
    ):
        raise ValueError("Değerlendirme DSN'i sorgu parametresiz yerel PostgreSQL olmalı.")
    return {"host": url.host, "port": url.port or 5432, "database": url.database}


def validate_database_dsns(database: str, admin: str, app: str, worker: str) -> dict[str, object]:
    import re

    from sqlalchemy.engine import make_url

    if not re.fullmatch(r"dou[a-z0-9_]{0,55}", database) or not any(
        word in database for word in ("eval", "inject", "acceptance")
    ):
        raise ValueError(
            "Yalnız dou ile başlayan açık eval/inject/acceptance veritabanı kullanılabilir."
        )
    identities = [database_identity(dsn) for dsn in (admin, app, worker)]
    if (
        any(identity != identities[0] for identity in identities)
        or identities[0]["database"] != database
    ):
        raise ValueError("Yönetici, uygulama ve işçi aynı izole veritabanı/host/porta bağlanmalı.")
    if make_url(app).username != "dou_app" or make_url(worker).username != "dou_worker":
        raise ValueError("Değerlendirme dou_app ve dou_worker rollerini kullanmalı.")
    if make_url(admin).username in {"dou_app", "dou_worker"}:
        raise ValueError("Kurulum bağlantısı uygulama/işçi rolü olamaz.")
    return identities[0]


def _psql(database: str, *args: str, pg_bin: str, admin_dsn: str) -> None:
    from sqlalchemy.engine import make_url

    url = make_url(admin_dsn)
    # libpq PGHOSTADDR/PGSERVICE can override the validated DSN. Inherit no PG routing.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env.update({"PGHOST": str(url.host), "PGPORT": str(url.port or 5432)})
    if url.username:
        env["PGUSER"] = url.username
    if url.password is not None:
        env["PGPASSWORD"] = url.password
    subprocess.run(
        [f"{pg_bin}/psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", database, *args],
        check=True,
        env=env,
    )


def prepare_database(database: str, *, recreate: bool, pg_bin: str, admin_dsn: str) -> None:
    def execute(target: str, *args: str) -> None:
        _psql(target, *args, pg_bin=pg_bin, admin_dsn=admin_dsn)

    if recreate:
        execute("postgres", "-c", f'DROP DATABASE IF EXISTS "{database}"')
    execute("postgres", "-c", f'CREATE DATABASE "{database}"')
    for migration in sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql")):
        execute(database, "-f", str(migration))
    # Explicit DSNs use pre-provisioned LOGIN roles; never change shared role passwords.
    execute(database, "-c", f'GRANT CONNECT ON DATABASE "{database}" TO dou_app, dou_worker')


def _embedding_runtime(provider: str) -> dict[str, str]:
    """Vektörü üreten kütüphanenin sürümü. Gerekçe için `summary` içindeki nota bakın."""
    from importlib.metadata import PackageNotFoundError, version

    packages = ["fastembed"] if provider == "fastembed" else ["onnxruntime", "tokenizers"]
    runtime: dict[str, str] = {}
    for package in packages:
        try:
            runtime[package] = version(package)
        except PackageNotFoundError:  # pragma: no cover
            runtime[package] = "kurulu değil"
    return runtime


def install_embedding_override(name: str | None) -> tuple[str, str] | None:
    """Ölçüme özgü bir embedding sağlayıcısını üretim kancasına takar (T045).

    `EMBEDDING_PROVIDER` ayarı yalnız `fastembed` ve `hashing` tanır ve o liste
    üretimindir; `config.py` bu şeridin dosyası değil. bge-m3 bir ADAY, bir üretim
    seçeneği değil — o yüzden ayar şemasına eklenmedi, buradan enjekte ediliyor.
    Dönen çift, sonuç dosyasına yazılacak (sağlayıcı, model) adıdır.
    """
    if name is None:
        return None
    if name != "bge-m3":
        raise SystemExit(f"bilinmeyen embedding override: {name!r} (yalnız 'bge-m3')")
    ensure_api_on_path()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app.modules.ingestion.embedding import set_embedding_provider
    from embedding_bge_m3 import BgeM3OnnxProvider

    provider = BgeM3OnnxProvider()
    set_embedding_provider(provider)
    return "bge-m3-onnx", provider.name


async def list_corpus_documents(
    client: Any, course_id: UUID, headers: dict[str, str]
) -> list[dict[str, object]]:
    """Consume the production page envelope without dropping later documents."""
    documents = []
    cursor = None
    seen: set[str] = set()
    while True:
        params = {"limit": "100"}
        if cursor:
            params["cursor"] = cursor
        response = await client.get(
            f"/courses/{course_id}/documents", headers=headers, params=params
        )
        response.raise_for_status()
        page = response.json()
        documents.extend(page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            return documents
        if cursor in seen:
            raise ValueError("Belge sayfalama imleci tekrarlanıyor; korpus özeti tamamlanamadı.")
        seen.add(cursor)


async def build(
    material: Path,
    storage_root: Path,
    admin_dsn: str,
    embedding_override: str | None = None,
    extra_material: Path | None = None,
) -> dict[str, object]:
    """Dersi açar, materyali yükler, worker'ı boşaltır ve korpusu özetler."""
    ensure_api_on_path()
    from app import worker
    from app.core.config import get_settings
    from app.core.db import dispose_engine, rls_session
    from app.main import create_app
    from app.modules.ingestion.storage import LocalFileStorage, set_storage
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    set_storage(LocalFileStorage(storage_root))
    override = install_embedding_override(embedding_override)

    # Eğitmen profili sahip bağlantısıyla yazılır: profiles'a INSERT politikası yoktur
    # (kayıt üretimde Supabase Auth köprüsünden gelir), yani `dou_app` bu satırı
    # yazamaz — doğrusu da bu.
    instructor_id = uuid4()
    student_id = uuid4()
    admin_engine = create_async_engine(admin_dsn)
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO profiles (id, email, full_name) VALUES (:id, :email, :name)"),
            [
                {"id": instructor_id, "email": INSTRUCTOR_EMAIL, "name": "Ayşe Hoca"},
                {
                    "id": student_id,
                    "email": "eval.ogrenci@dogus.edu.tr",
                    "name": "Örnek Öğrenci",
                },
            ],
        )
    await admin_engine.dispose()

    headers = {"Authorization": f"Bearer dev:{instructor_id}"}
    app = create_app()
    summary: dict[str, object]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://corpus") as client:
        response = await client.post(
            "/courses",
            json={"code": COURSE_CODE, "title": COURSE_TITLE},
            headers=headers,
        )
        response.raise_for_status()
        course_id = UUID(response.json()["id"])
        membership = await client.post(
            f"/courses/{course_id}/members",
            json={"email": "eval.ogrenci@dogus.edu.tr", "role": "student"},
            headers=headers,
        )
        membership.raise_for_status()

        uploaded: list[str] = []
        source_manifest: list[dict[str, str]] = []
        # `extra_material` T046 içindir: zehirli belge ölçüm materyalinin YANINA yüklenir
        # ama `sample_data/` içine KONMAZ. Konsaydı ölçüm korpusuna da girer ve Recall
        # ile citation precision sayıları zehirli metinle kirlenirdi.
        # ASYNC240: dizin listeleme ve dosya okuma bloklar ama bu tek seferlik bir
        # kurulum betiği; eşzamanlı başka bir iş yok ve anyio bağımlılığı eklemek
        # maliyeti karşılamaz.
        sources = sorted(material.iterdir())
        if extra_material is not None:
            sources += sorted(extra_material.iterdir())
        for path in sources:
            if path.suffix.lower() not in CORPUS_SUFFIXES:
                continue
            with path.open("rb") as handle:
                source_bytes = handle.read()
                response = await client.post(
                    f"/courses/{course_id}/documents",
                    files={"file": (path.name, source_bytes)},
                    headers=headers,
                )
            response.raise_for_status()
            uploaded.append(path.name)
            source_manifest.append(
                {"file_name": path.name, "sha256": hashlib.sha256(source_bytes).hexdigest()}
            )

        # Yükleme ucu worker'ı arka planda tetikler ama ASGI test taşımasında arka plan
        # görevlerinin bitmesi garanti değil; kuyruk burada açıkça boşaltılır.
        while await worker.drain():
            pass
        await worker.dispose()

        documents = await list_corpus_documents(client, course_id, headers)
        summary = {
            "course_id": str(course_id),
            "instructor_id": str(instructor_id),
            "student_id": str(student_id),
            # Korpusun HANGİ VERİTABANINDA durduğu özete yazılır. Yazılmadığı sürece
            # `evaluate.py` .env'deki geliştirme veritabanına bağlanıp bu course_id'ye
            # ait hiçbir chunk bulamıyor, hata da vermiyordu: her soru 0 sonuç dönüyor,
            # Recall 0.000 olarak dosyaya yazılıyordu. Sessizce yanlış sayı üreten bir
            # koşu, hiç koşmayandan kötüdür.
            "database_identity": database_identity(str(settings.database_url)),
            "embedding_provider": override[0] if override else settings.embedding_provider,
            "embedding_model": override[1] if override else settings.embedding_model,
            # Vektörü ÜRETEN kütüphanenin sürümü. Sağlayıcı adı yetmiyor: fastembed
            # 0.5.1'den sonra e5-large'ı CLS yerine mean pooling ile kuruyor ve bu bir
            # vektör uzayı değişikliği. Aynı "fastembed" adıyla iki farklı uzay
            # üretilebiliyor; korpus hangisiyle gömüldüğünü kendi taşımalı, yoksa
            # üzerinde ölçülen hiçbir sayı yeniden üretilemez (12_R2_OLCUM.md eki).
            "embedding_runtime": _embedding_runtime(
                override[0] if override else settings.embedding_provider
            ),
            "uploaded": uploaded,
            "source_manifest": source_manifest,
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
        "--pg-bin",
        default=os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin"),
    )
    parser.add_argument(
        "--admin-dsn",
        help="Sahip/superuser bağlantısı (profiles seed'i için). Varsayılan: yerel superuser.",
    )
    parser.add_argument("--app-dsn", default=os.environ.get("EVAL_APP_DSN"))
    parser.add_argument("--worker-dsn", default=os.environ.get("EVAL_WORKER_DSN"))
    parser.add_argument("--out", type=Path, help="Özeti bu dosyaya JSON olarak yaz.")
    parser.add_argument(
        "--extra-material",
        type=Path,
        help="Ek materyal dizini (T046 zehirli belgesi). Ölçüm korpusunda kullanılmaz.",
    )
    parser.add_argument(
        "--embedding-override",
        choices=("bge-m3",),
        help="Ölçüme özgü embedding sağlayıcısı (T045 adayı). Üretim ayarını değiştirmez.",
    )
    args = parser.parse_args(argv)
    admin_dsn = args.admin_dsn or os.environ.get("EVAL_ADMIN_DSN")
    if not admin_dsn or not args.app_dsn or not args.worker_dsn:
        parser.error("Açık --admin-dsn, --app-dsn ve --worker-dsn (veya EVAL_*_DSN) gerekir.")
    try:
        validate_database_dsns(args.database, admin_dsn, args.app_dsn, args.worker_dsn)
    except (ValueError, TypeError):
        parser.error("Üç DSN aynı izole yerel eval veritabanını ve doğru rolleri göstermeli.")
    if not args.skip_setup:
        prepare_database(
            args.database,
            recreate=args.recreate,
            pg_bin=args.pg_bin,
            admin_dsn=admin_dsn,
        )
    os.environ["DATABASE_URL"] = args.app_dsn
    os.environ["WORKER_DATABASE_URL"] = args.worker_dsn
    os.environ["DEV_AUTH_ENABLED"] = "true"
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    ensure_api_on_path()
    from app.core.config import get_settings

    get_settings.cache_clear()

    summary = asyncio.run(
        build(
            args.material,
            args.storage_root,
            admin_dsn,
            args.embedding_override,
            args.extra_material,
        )
    )

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
