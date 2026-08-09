#!/usr/bin/env python3
"""Gold set denetimi — koşudan önce çalışır, koşuyu koşulsuz durdurabilir.

Üç ayrı soruyu birbirinden ayrı yanıtlar:

1. **Yapısal** — id tekrarı, eksik alan, kapalı değer kümesi dışı davranış,
   kategori sayımı, elle yazılmış chunk UUID'si.
2. **Ayrık mı** — kalibrasyon ve holdout id ve normalize edilmiş soru metni
   düzeyinde kesişiyor mu. Kesişiyorsa raporlanan her sayı geçersizdir
   (Anayasa III), o yüzden bu hata ölümcüldür.
3. **Kaynak gerçek mi** — `expected_sources` içindeki her (dosya, sayfa/slayt)
   çifti gerçekten var mı. Kontrol, materyali ÜRETİM ayrıştırıcısıyla
   (`app.modules.ingestion.parsers.parse`) okuyarak yapılır; sayfa numarası
   tahminle değil, ingest'in gerçekten üreteceği numarayla doğrulanır.

Neden veritabanı gerekmiyor: chunk'ın `page_number`/`slide_number`/`section_title`
alanları ayrıştırıcıdan gelir ve chunking bunları değiştirmez (chunking.py: bir
chunk iki sayfayı birleştirmez). Yani ayrıştırıcı çıktısı, ingest sonrası oluşacak
konum kümesinin birebir aynısıdır. İngest sonrası ayrıca doğrulamak istersen
`--db` ile gerçek korpusa da sorabilirsin.

Kullanım:

    cd apps/api && uv run python ../../evaluation/verify_gold_set.py
    cd apps/api && uv run python ../../evaluation/verify_gold_set.py --corpus corpus.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import goldset
from _paths import DEFAULT_MATERIAL_DIR, GOLD_SET_DIR, ensure_api_on_path

# Ayrıştırıcının tanıdığı ve gold set'te kaynak olarak gösterilebilecek uzantılar.
_MATERIAL_SUFFIXES = frozenset({".pdf", ".pptx", ".md", ".txt", ".py", ".c", ".h", ".java"})


@dataclass(frozen=True, slots=True)
class MaterialLocation:
    """Materyalde gerçekten var olan tek bir konum."""

    file_name: str
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    text: str


def load_material(directory: Path, *, only_ingested: bool) -> list[MaterialLocation]:
    """Materyal klasörünü üretim ayrıştırıcısıyla okur.

    `only_ingested=True` iken `.md` dosyaları atlanır: pakette hem `01-processes.md`
    hem `01-processes.pdf` var ve derse yüklenen PDF'tir. Markdown kaynak metindir,
    korpusa girmez; gold set kaynağı olarak gösterilirse ingest'te karşılığı çıkmaz.
    """
    ensure_api_on_path()
    from app.modules.ingestion.parsers import parse

    locations: list[MaterialLocation] = []
    for path in sorted(directory.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in _MATERIAL_SUFFIXES:
            continue
        if only_ingested and suffix == ".md":
            continue
        document = parse(path.read_bytes(), suffix)
        for block in document.blocks:
            locations.append(
                MaterialLocation(
                    file_name=path.name,
                    page_number=block.page_number,
                    slide_number=block.slide_number,
                    section_title=block.section_title,
                    text=block.text,
                )
            )
    return locations


def source_errors(gold: goldset.GoldSet, locations: list[MaterialLocation]) -> list[str]:
    """Karşılığı olmayan her `expected_sources` girdisini raporlar."""
    known_files = {location.file_name for location in locations}
    errors: list[str] = []
    for item in gold.items:
        for source in item.expected_sources:
            if source.file_name not in known_files:
                errors.append(
                    f"{item.id}: '{source.file_name}' materyalde yok "
                    f"(bilinen dosyalar: {sorted(known_files)})"
                )
                continue
            hit = any(
                source.matches(
                    file_name=location.file_name,
                    page_number=location.page_number,
                    slide_number=location.slide_number,
                    section_title=location.section_title,
                    text=location.text,
                )
                for location in locations
            )
            if not hit:
                errors.append(f"{item.id}: kaynak '{source.label()}' materyalde karşılık bulmuyor.")
    return errors


async def db_source_errors(gold: goldset.GoldSet, course_id: str, as_user: str) -> list[str]:
    """İngest sonrası gerçek korpusa karşı aynı kontrol.

    Ayrıştırıcı kontrolü ingest'in ne ÜRETECEĞİNİ doğrular; bu kontrol neyin
    gerçekten ÜRETİLDİĞİNİ doğrular. İkisi ayrıdır: dosya yüklenmemişse veya
    işleme yarıda kalmışsa yalnız bu ikincisi yakalar.

    Sorgu `rls_session` ile, yani dersin bir ÜYESİ olarak koşar. Bağlamsız bir
    `dou_app` bağlantısı hiçbir satır göremez (fail-closed) ve kontrol "korpus boş"
    diye yanlış alarm verirdi — ilk yazışında tam bunu yaptı. Üye bağlamıyla koşmak
    ayrıca doğru olanı ölçer: gold set, sistemin öğrenciye gösterebildiği chunk'lara
    karşı doğrulanmalı, sahibin gördüğü ham tabloya karşı değil.
    """
    ensure_api_on_path()
    from app.core.db import dispose_engine, rls_session
    from sqlalchemy import text as sql_text

    try:
        async with rls_session(UUID(as_user)) as session:
            rows = (
                await session.execute(
                    sql_text(
                        "SELECT d.file_name, c.page_number, c.slide_number, "
                        "       c.section_title, c.text "
                        "FROM chunks c JOIN documents d ON d.id = c.document_id "
                        "WHERE c.course_id = :course_id"
                    ),
                    {"course_id": course_id},
                )
            ).all()
    finally:
        await dispose_engine()

    locations = [
        MaterialLocation(
            file_name=row[0],
            page_number=row[1],
            slide_number=row[2],
            section_title=row[3],
            text=row[4],
        )
        for row in rows
    ]
    if not locations:
        return [
            f"Derste ({course_id}) hiç chunk görünmüyor. İki olasılık var: materyal "
            f"yüklenmemiş olabilir, ya da --as-user ({as_user}) bu dersin üyesi değildir "
            "ve RLS satırları gizliyordur."
        ]
    return source_errors(gold, locations)


def _report(title: str, errors: list[str]) -> bool:
    if errors:
        print(f"\nFAIL  {title} ({len(errors)} sorun)")
        for error in errors:
            print(f"  - {error}")
        return False
    print(f"PASS  {title}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gold set denetimi")
    parser.add_argument("--gold-set-dir", type=Path, default=GOLD_SET_DIR)
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL_DIR)
    parser.add_argument(
        "--include-markdown",
        action="store_true",
        help="Korpusa .md dosyaları da yüklendiyse aç (varsayılan: yalnız PDF/PPTX/kod).",
    )
    parser.add_argument("--db", action="store_true", help="İngest sonrası gerçek korpusa da sor.")
    parser.add_argument("--course-id", help="--db ile birlikte zorunlu (ya da --corpus).")
    parser.add_argument("--as-user", help="Sorgunun koşacağı üye kimliği (--db ile).")
    parser.add_argument(
        "--corpus",
        type=Path,
        help="build_corpus.py özet JSON'u; course_id ve as_user'ı buradan alır.",
    )
    args = parser.parse_args(argv)

    if args.corpus:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        args.course_id = args.course_id or corpus["course_id"]
        args.as_user = args.as_user or corpus["instructor_id"]
        args.db = True

    calibration = goldset.load(args.gold_set_dir / "calibration.json")
    holdout = goldset.load(args.gold_set_dir / "holdout.json")

    print(f"kalibrasyon: {len(calibration.items)} soru · holdout: {len(holdout.items)} soru")
    for gold in (calibration, holdout):
        counts = gold.by_category()
        summary = " · ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        print(f"  {gold.name}: {summary}")

    ok = True
    ok &= _report("kalibrasyon yapısal", goldset.structural_errors(calibration))
    ok &= _report("holdout yapısal", goldset.structural_errors(holdout))
    ok &= _report("kalibrasyon ↔ holdout ayrıklığı", goldset.overlap_errors(calibration, holdout))

    locations = load_material(args.material, only_ingested=not args.include_markdown)
    print(f"materyal: {args.material} — {len(locations)} konum ayrıştırıldı")
    ok &= _report("kalibrasyon kaynakları (ayrıştırıcı)", source_errors(calibration, locations))
    ok &= _report("holdout kaynakları (ayrıştırıcı)", source_errors(holdout, locations))

    if args.db:
        if not args.course_id or not args.as_user:
            parser.error("--db için --course-id ve --as-user (ya da --corpus) gerekir.")
        import asyncio

        ok &= _report(
            "kalibrasyon kaynakları (korpus)",
            asyncio.run(db_source_errors(calibration, args.course_id, args.as_user)),
        )
        ok &= _report(
            "holdout kaynakları (korpus)",
            asyncio.run(db_source_errors(holdout, args.course_id, args.as_user)),
        )

    print("\nSONUÇ:", "temiz" if ok else "DÜZELTİLMELİ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
