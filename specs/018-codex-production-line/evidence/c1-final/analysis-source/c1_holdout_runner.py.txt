"""Aynı gerçek ingestion korpusunda iki retrieval kaynağını karşılaştırır.

Yalnız /private/tmp kanıt dizinine yazar; DB kurmaz, kaynak dosyası değiştirmez.
Hashing sonucu anlamsal kalite/kabul sertifikası değildir. LLM hiç çağrılmaz.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import UUID

REPO = Path("/Users/muratates/code/dou-synapse-018-codex-production-line")
EVIDENCE = Path("/private/tmp/dou018-evidence")
BASE = "71d5ff640f0d48a08f3967b000485a15035f10c7"
RETRIEVAL = Path("apps/api/app/modules/retrieval")
FILES = [RETRIEVAL / (name + ".py") for name in ("dense", "fts", "service")]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=True).stdout


def install_paths() -> None:
    for path in (REPO / "evaluation", REPO / "apps/api", REPO):
        sys.path.insert(0, str(path))


def load_baseline(snapshot_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Git'teki gerçek kaynakları ayrı modüllere yükler; algoritma yeniden yazılmaz."""
    modules, manifest = {}, {}
    snapshot_dir.mkdir()
    for path in FILES:
        body = git("show", f"{BASE}:{path}")
        target = snapshot_dir / path.name
        target.write_bytes(body)
        name = "_c1_baseline_" + path.stem
        module = types.ModuleType(name)
        module.__file__ = str(target)
        sys.modules[name] = module
        exec(compile(body, str(target), "exec"), module.__dict__)
        modules[path.stem] = module
        manifest[str(path)] = {"sha256": sha(body), "snapshot": str(target)}
    # Eski service importları aday şeritlere bağlanmış olabilir; yalnız ayrı eski
    # modülün globals'ı, aynı git kaynağından yüklenen iki gerçek işleve bağlanır.
    modules["service"].dense_search = modules["dense"].dense_search
    modules["service"].fts_search = modules["fts"].fts_search
    assert (
        modules["service"].HybridRetriever.search.__globals__["dense_search"]
        is modules["dense"].dense_search
    )
    assert (
        modules["service"].HybridRetriever.search.__globals__["fts_search"]
        is modules["fts"].fts_search
    )
    return modules, manifest


def validate_target(raw: str, corpus: dict[str, Any], role: str = "dou_app") -> dict[str, Any]:
    """Bu deney yalnız mevcut sunucudaki açık, benzersiz eval hedefine bağlanır."""
    try:
        url = urlsplit(raw)
        identity = {"host": url.hostname, "port": url.port, "database": url.path[1:]}
        if (
            url.scheme not in {"postgresql", "postgresql+psycopg"}
            or url.hostname != "127.0.0.1"
            or url.port != 55448
            or unquote(url.username or "") != role
            or not re.fullmatch(r"/dou018_eval_[a-z0-9][a-z0-9_]{7,31}", url.path)
            or url.query
            or url.fragment
            or "?" in raw
            or "#" in raw
            or any(c.isspace() for c in raw)
            or identity != corpus.get("database_identity")
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError(
            "Açık dou_app/127.0.0.1:55448/dou018_eval_* DSN ve korpus kimliği gerekir."
        ) from None
    if {
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGHOSTADDR",
        "PGOPTIONS",
        "PGSYSCONFDIR",
    } & os.environ.keys():
        raise ValueError("Libpq yönlendirme seçenekleri bu deneyde kullanılamaz.")
    return {**identity, "user": role}


def validate_corpus(corpus: dict[str, Any]) -> None:
    import build_corpus

    if corpus.get("embedding_provider") != "hashing" or not corpus.get("student_id"):
        raise ValueError("Gerçek kurucudan hashing korpusu ve öğrenci kimliği gerekir.")
    UUID(corpus["course_id"])
    UUID(corpus["student_id"])
    source = [
        {"file_name": p.name, "sha256": sha(p.read_bytes())}
        for p in sorted(build_corpus.DEFAULT_MATERIAL_DIR.iterdir())
        if p.suffix.lower() in build_corpus.CORPUS_SUFFIXES
    ]
    if source != corpus.get("source_manifest"):
        raise ValueError("Korpus mevcut sabit materyal paketinin kaynak hashleriyle eşleşmiyor.")
    if not corpus.get("documents") or any(d["status"] != "completed" for d in corpus["documents"]):
        raise ValueError("Korpus belgeleri eksiksiz tamamlanmış olmalı.")


def offline_manifest(output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    import backends
    import evaluate
    import goldset
    from app.modules.retrieval import dense, fts, service

    modules, sources = load_baseline(output / "baseline-source")
    current_refs = (dense.dense_search, fts.fts_search, service.dense_search, service.fts_search)
    saved = backends.RETRIEVAL_ENTRY_POINTS["hybrid"]
    resolutions = {}
    try:
        for arm, entry, expected in [
            (
                "baseline",
                "_c1_baseline_service:HybridRetriever",
                modules["service"].HybridRetriever,
            ),
            ("candidate", "app.modules.retrieval.service:HybridRetriever", service.HybridRetriever),
        ]:
            backends.RETRIEVAL_ENTRY_POINTS["hybrid"] = (entry,)
            found, actual_entry = backends.resolve_retrieval_callable("hybrid")
            if found is not expected or actual_entry != entry:
                raise ValueError("Mevcut harness yanlış retrieval girişine bağlandı.")
            backend = backends.RetrievalBackend("hybrid", as_user=UUID(int=1), top_k=8)
            if backend.calls_llm:
                raise ValueError("LLM çağıran katman bu deneyde kullanılamaz.")
            resolutions[arm] = entry
    finally:
        backends.RETRIEVAL_ENTRY_POINTS["hybrid"] = saved
    assert current_refs == (
        dense.dense_search,
        fts.fts_search,
        service.dense_search,
        service.fts_search,
    )
    assert service.dense_search is dense.dense_search and service.fts_search is fts.fts_search
    calibration = goldset.load(REPO / "evaluation/gold_set/calibration.json")
    holdout = goldset.load(REPO / "evaluation/gold_set/holdout.json")
    if goldset.structural_errors(holdout) or goldset.overlap_errors(calibration, holdout):
        raise ValueError("Holdout yapısı veya kalibrasyon ayrıklığı geçersiz.")
    items = evaluate.select_items(holdout, "retrieval", None)
    shared = [
        Path("apps/api/app/contracts.py"),
        Path("apps/api/app/core/db.py"),
        Path("apps/api/app/core/config.py"),
        Path("apps/api/app/core/vector_space.py"),
        Path("apps/api/app/modules/ingestion/embedding.py"),
        RETRIEVAL / "fusion.py",
        RETRIEVAL / "scope.py",
    ]
    eval_files = [
        "build_corpus.py",
        "evaluate.py",
        "backends.py",
        "metrics.py",
        "goldset.py",
        "provenance.py",
        "gold_set/calibration.json",
        "gold_set/holdout.json",
    ]
    manifest = {
        "baseline_commit": BASE,
        "candidate_checkout_head": git("rev-parse", "HEAD").decode().strip(),
        "candidate_dirty": bool(git("status", "--porcelain")),
        "baseline_source": sources,
        "candidate_source_sha256": {str(p): sha((REPO / p).read_bytes()) for p in FILES},
        "common_dependency_source_sha256": {str(p): sha((REPO / p).read_bytes()) for p in shared},
        "harness_source_sha256": {
            f"evaluation/{p}": sha((REPO / "evaluation" / p).read_bytes()) for p in eval_files
        },
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "resolver_entries": resolutions,
        "holdout_total_items": len(holdout.items),
        "retrieval_asked": len(items),
        "retrieval_scored": sum(i.is_retrieval_scored for i in items),
        "query_selection_sha256": sha(
            json.dumps([(i.id, i.question) for i in items], ensure_ascii=False).encode()
        ),
        "adapter_contract": [
            "Baseline üç kaynak git show ile byte-for-byte saklandı ve ayrı modüllere yüklendi.",
            "Yalnız baseline service globals dense_search/fts_search eski gerçek işlevlere bağlandı.",
            "Aday normal service; uygulama kaynak dosyaları veya normal modül işlevleri değiştirilmedi.",
            "Backends resolver giriş listesi süreç içinde değişip finally ile geri alınır.",
            "Ortak Settings/embedding/fusion/scope/db/contracts ve değerlendirme harness kaynakları iki kolda aynıdır.",
            "Bu bütün eski uygulama karşılaştırması değil, üç retrieval dosyasının aynı güncel çevrede karşılaştırmasıdır.",
            "Harness raw git_sha checkout bilgisidir; baseline algoritma SHA bilgisini bu companion manifest verir.",
        ],
        "limitations": [
            "Hashing deterministik mekanik regresyon verisidir; E5/LLM anlamsal kalite veya öğretmen kabulü değildir.",
            "LLM çağrısı yoktur; retrieval katmanı ham HybridRetriever sonuçlarını ölçer.",
            "Performans veya gecikme kazancı bu holdouttan iddia edilmez.",
            "Harness eşik taramasını ham sonuçta hesaplar; bu deney eşik seçmez veya değiştirmez.",
            "Kirli aday commit SHA ile tek başına temsil edilmez; çalışma ağacı kaynak hashleri esastır.",
            "Holdout üzerindeki insan kaynak/içerik değerlendirmesi bu çalışmayla tamamlanmış sayılmaz.",
        ],
    }
    return modules, manifest


async def corpus_state(engine: Any, corpus: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.db import set_rls_context
    from app.core.vector_space import current_space

    async with AsyncSession(bind=engine) as session, session.begin():
        await session.execute(text("SET TRANSACTION READ ONLY"))
        await set_rls_context(session, UUID(corpus["student_id"]))
        ident = dict(
            (
                await session.execute(
                    text(
                        "SELECT current_database() AS database, current_user AS role, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
                    )
                )
            )
            .mappings()
            .one()
        )
        if ident["role"] != "dou_app" or ident["rolsuper"] or ident["rolbypassrls"]:
            raise ValueError("Gerçek dou_app öğrenci RLS rolü gerekir.")
        if (await session.execute(text("SHOW transaction_read_only"))).scalar_one() != "on":
            raise ValueError("Salt okunur işlem gerekir.")
        rows = (
            (
                await session.execute(
                    text("""SELECT c.id,c.document_id,c.chunk_index,c.text,
            c.page_number,c.slide_number,c.section_title,c.embedding::text AS vector,
            c.embedding_space,d.file_name,d.file_hash FROM chunks c JOIN documents d
            ON d.id=c.document_id WHERE c.course_id=:course ORDER BY c.id"""),
                    {"course": UUID(corpus["course_id"])},
                )
            )
            .mappings()
            .all()
        )
        if len(rows) != sum(x["chunks"] for x in corpus["chunks"]) or not rows:
            raise ValueError("Öğrencinin gördüğü korpus sayısı kurulum özetiyle eşleşmiyor.")
        if {row["embedding_space"] for row in rows} != {current_space()}:
            raise ValueError("Korpus/query kanonik hashing uzayı uyuşmuyor.")
        sources = {item["file_name"]: item["sha256"] for item in corpus["source_manifest"]}
        if any(sources.get(row["file_name"]) != row["file_hash"] for row in rows):
            raise ValueError("DB kaynak hashleri gerçek upload manifestiyle uyuşmuyor.")
        policies = (
            await session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE oid IN ('public.chunks'::regclass, 'public.documents'::regclass)"
                )
            )
        ).all()
        if len(policies) != 2 or any(not row[0] or not row[1] for row in policies):
            raise ValueError("İki kaynak tablosunda zorunlu RLS korunmalı.")
        return {
            **ident,
            "rows": len(rows),
            "namespace": current_space(),
            "content_vector_metadata_sha256": sha(
                json.dumps(
                    [dict(row) for row in rows], sort_keys=True, default=str, ensure_ascii=False
                ).encode()
            ),
        }


def readonly_engine() -> Any:
    from sqlalchemy import event
    from app.core.db import get_engine

    engine = get_engine()

    @event.listens_for(engine.sync_engine, "do_connect")
    def readonly_route(dialect: Any, record: Any, args: Any, params: dict[str, Any]) -> None:
        params.update(
            hostaddr="127.0.0.1",
            passfile=os.devnull,
            sslmode="disable",
            connect_timeout=5,
            options="-c default_transaction_read_only=on -c statement_timeout=120000 -c lock_timeout=5000",
        )

    return engine


async def run_pair(output: Path, corpus_path: Path, manifest: dict[str, Any]) -> None:
    import backends
    import evaluate
    from app.core.config import get_settings
    from app.core.db import dispose_engine
    from app.modules.ingestion.embedding import get_embedding_provider

    manifest["phase"] = "validate_corpus"
    corpus = json.loads(corpus_path.read_text())
    validate_corpus(corpus)
    target = validate_target(os.environ.get("EVAL_APP_DSN", ""), corpus)
    validate_target(os.environ.get("EVAL_WORKER_DSN", ""), corpus, "dou_worker")
    os.environ["DATABASE_URL"] = os.environ["EVAL_APP_DSN"]
    os.environ["WORKER_DATABASE_URL"] = os.environ["EVAL_WORKER_DSN"]
    get_settings.cache_clear()
    settings = get_settings()
    manifest.update(
        corpus_path=str(corpus_path),
        corpus_sha256=sha(corpus_path.read_bytes()),
        target=target,
        common_retrieval={
            key: getattr(settings, key)
            for key in [
                "retrieval_top_k",
                "retrieval_dense_candidates",
                "retrieval_dense_candidate_multiplier",
                "retrieval_fts_candidates",
                "retrieval_rrf_k",
                "evidence_threshold",
            ]
        },
        actual_embedding={
            "class": type(get_embedding_provider()).__name__,
            "name": get_embedding_provider().name,
        },
        quality_reportable=False,
        provider_calls=0,
        arms={},
    )
    if settings.embedding_provider != "hashing" or settings.retrieval_top_k != 8:
        raise ValueError("Bu sabit deney hashing ve top_k=8 gerektirir.")
    saved = backends.RETRIEVAL_ENTRY_POINTS["hybrid"]
    states = []
    try:
        for arm in ("baseline", "candidate"):
            manifest["phase"] = "run_" + arm
            entry = manifest["resolver_entries"][arm]
            backends.RETRIEVAL_ENTRY_POINTS["hybrid"] = (entry,)
            arm_dir = output / arm
            args = evaluate.parse_args(
                [
                    "--set",
                    "holdout",
                    "--layer",
                    "retrieval",
                    "--mode",
                    "hybrid",
                    "--corpus",
                    str(corpus_path),
                    "--results-dir",
                    str(arm_dir),
                    "--concurrency",
                    "1",
                    "--no-resume",
                ]
            )
            # Varsayılan prepare_threshold korunur; yalnız bağlanılan oturum salt okunurdur.
            engine = readonly_engine()
            before = await corpus_state(engine, corpus)
            if states and before != states[0]:
                raise ValueError("İki kolun korpusu aynı değil.")
            states.append(before)
            log = io.StringIO()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                code = await evaluate.execute(args)
            (output / f"{arm}.log").write_text(log.getvalue())
            if code != 0:
                raise RuntimeError("Mevcut evaluate harness kolu tamamlanmadı.")
            results = list(arm_dir.glob("*.json"))
            if len(results) != 1:
                raise ValueError("Her kolda tek yeni ham sonuç gerekir.")
            result = json.loads(results[0].read_text())
            if (
                result["entry_point"] != entry
                or result["runner"]["failures"]
                or result["runner"]["retries"]
            ):
                raise ValueError("Eksiksiz, doğru girişli ve retriesiz retrieval koşusu gerekir.")
            if (
                result["n_items"] != manifest["retrieval_asked"]
                or result["metrics"]["n_items"] != manifest["retrieval_scored"]
            ):
                raise ValueError("Holdout soru kümesi eksik.")
            # execute motoru kapatır; kontrol için yeni salt okunur motor oluşturulur.
            after = await corpus_state(readonly_engine(), corpus)
            await dispose_engine()
            if before != after:
                raise ValueError("Retrieval korpus verisini değiştirdi.")
            manifest["arms"][arm] = {
                "raw_result": str(results[0]),
                "sha256": sha(results[0].read_bytes()),
                "corpus_state_before_after": before,
                "recall_at_5": result["metrics"]["recall_at_5"],
                "mrr": result["metrics"]["mrr"],
                "retrieval": result["retrieval"],
                "config_fingerprint": result["config_fingerprint"],
            }
        left, right = (manifest["arms"][name] for name in ("baseline", "candidate"))
        if (
            left["retrieval"] != right["retrieval"]
            or left["config_fingerprint"] != right["config_fingerprint"]
        ):
            raise ValueError("İki kolda ortak yapılandırma değişti.")
        with contextlib.redirect_stdout(io.StringIO()):
            code = evaluate.compare_runs(
                Path(left["raw_result"]), Path(right["raw_result"]), output / "paired"
            )
        if code != 0:
            raise RuntimeError("Mevcut eşleştirilmiş karşılaştırıcı tamamlanmadı.")
        manifest["numeric_delta"] = {k: right[k] - left[k] for k in ("recall_at_5", "mrr")}
        manifest["mechanical_nonregression"] = all(
            delta >= 0 for delta in manifest["numeric_delta"].values()
        )
        for field in [
            "candidate_source_sha256",
            "common_dependency_source_sha256",
            "harness_source_sha256",
        ]:
            if any(
                sha((REPO / path).read_bytes()) != value for path, value in manifest[field].items()
            ):
                raise ValueError("Ölçüm sırasında kaynak değişti.")
        manifest["status"] = "measured_hashing_only"
        manifest["phase"] = "complete"
    finally:
        backends.RETRIEVAL_ENTRY_POINTS["hybrid"] = saved
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(EVIDENCE) or output == EVIDENCE:
        parser.error("Yeni çıktı dizini /private/tmp/dou018-evidence altında olmalı.")
    output.mkdir(exist_ok=False)
    # Anahtarlar yalnız bu ayrı süreçte boşaltılır; kaynak .env dosyalarına yazılmaz.
    os.environ.update(
        ENVIRONMENT="local",
        DEV_AUTH_ENABLED="true",
        EMBEDDING_PROVIDER="hashing",
        LLM_FAKE_PROVIDER="true",
        GROQ_API_KEY="",
        GEMINI_API_KEY="",
        OPENAI_API_KEY="",
        RETRIEVAL_TOP_K="8",
        RETRIEVAL_DENSE_CANDIDATES="24",
        RETRIEVAL_DENSE_CANDIDATE_MULTIPLIER="8",
        RETRIEVAL_FTS_CANDIDATES="24",
        RETRIEVAL_RRF_K="60",
    )
    install_paths()
    manifest: dict[str, Any] = {"status": "planned", "execute": args.execute}
    try:
        _, details = offline_manifest(output)
        manifest.update(details)
        if args.execute:
            if args.corpus is None:
                raise ValueError("Gerçek kurucu korpus özeti gerekir.")
            asyncio.run(run_pair(output, args.corpus.resolve(), manifest))
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return 1 if manifest["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
