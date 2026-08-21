"""Bir dersteki sorular için kanıt eşiğinin ne yaptığını ÖLÇER.

## Neden var

`fill_answer_cache.py` (T053) provasında 14 demo sorusundan ikisi, doğru belge
zaten en iyi sonuç olarak bulunmuşken reddedildi. Sebebi görmek için skorların
kendisine bakmak gerekti; bu betik o bakışı tekrarlanabilir kılar (Anayasa III:
bir sayıyı raporluyorsan onu üreten komut da yanında olsun).

Ölçülen sinyal `dense_score`'dur — füzyon skoru değil. Kapı ikisine de aynı
yerden bakar (`api/chat.py::_has_evidence` ve `retrieval/service.retrieve`).

## Kullanım

    uv run python scripts/probe_evidence_threshold.py \\
        --course-id <uuid> --user-id <uuid> \\
        --questions scripts/demo_questions.json

Kapsam dışı sorular da okunur ve ayrı işaretlenir: eşiğin işe yarayıp
yaramadığı, "içerideki" ile "dışarıdaki" soruların skorları arasındaki ARALIĞA
bakılarak anlaşılır, tek bir sorunun skoruna bakılarak değil.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID


async def _measure(course_id: UUID, user_id: UUID, questions: list[tuple[str, bool]]) -> int:
    from app.core.config import get_settings
    from app.core.db import rls_session
    from app.modules.retrieval.service import HybridRetriever

    settings = get_settings()
    threshold = settings.evidence_threshold
    print(f"kanıt eşiği = {threshold}\n")
    print(f"{'skor':>8}  {'karar':<11} {'kapsam':<9} soru")

    in_scope: list[float] = []
    out_scope: list[float] = []

    async with rls_session(user_id) as session:
        retriever = HybridRetriever(session, settings)
        for question, expected_out_of_scope in questions:
            chunks = await retriever.search(
                course_id=course_id, query=question, limit=settings.retrieval_top_k
            )
            best = max((chunk.dense_score for chunk in chunks), default=0.0)
            (out_scope if expected_out_of_scope else in_scope).append(best)
            verdict = "GEÇER" if best >= threshold else "REDDEDİLİR"
            scope = "dışı" if expected_out_of_scope else "içi"
            source = chunks[0].file_name if chunks else "-"
            print(f"{best:8.4f}  {verdict:<11} {scope:<9} {question[:48]:<48} ← {source}")

    print()
    if in_scope and out_scope:
        # Ayrım payı: eşiğin güvenli oturabileceği aralık. Negatifse iki sınıf
        # ÜST ÜSTE BİNİYOR demektir ve hiçbir eşik ikisini temiz ayıramaz.
        margin = min(in_scope) - max(out_scope)
        print(f"kapsam içi en düşük : {min(in_scope):.4f}")
        print(f"kapsam dışı en yüksek: {max(out_scope):.4f}")
        print(f"ayrım payı           : {margin:+.4f}")
        if margin <= 0:
            print(
                "\nİKİ SINIF ÜST ÜSTE BİNİYOR: tek bir eşik bu soru kümesini temiz "
                "ayıramaz. Eşiği oynatmak yalnız hangi hatayı yapacağını seçer."
            )
    rejected = [score for score in in_scope if score < threshold]
    if rejected:
        print(
            f"\nUYARI: kapsam İÇİ {len(rejected)}/{len(in_scope)} soru reddedildi. "
            "Çevrimdışı demoda bu sorular cevaplanamaz."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", required=True, type=UUID)
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).with_name("demo_questions.json"),
    )
    args = parser.parse_args()

    spec = json.loads(args.questions.read_text(encoding="utf-8"))
    questions: list[tuple[str, bool]] = []
    for entry in spec["courses"]:
        questions += [(question, False) for question in entry.get("questions", [])]
        questions += [(question, True) for question in entry.get("out_of_scope_questions", [])]

    return asyncio.run(_measure(args.course_id, args.user_id, questions))


if __name__ == "__main__":
    sys.exit(main())
