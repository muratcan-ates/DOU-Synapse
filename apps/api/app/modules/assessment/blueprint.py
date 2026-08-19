"""Blueprint iş kuralları: dağılım doğrulaması, yayın kapısı, dondurma (002 US3).

Router'a gömülmedi çünkü buradaki üç karar da uçtan bağımsız sınanabilir olmalı:
FR-112'nin tutarlılık doğrulaması, FR-114'ün eksik hücre raporu ve yayın anındaki
dondurma. Uç yalnız bunları çağırır.

**Metinler burada üretilir, istemcide değil.** Anayasa V: "backend tek hata zarfı
üretir; frontend kendi hata metnini uydurmaz". Hücre adı ("CO1 · zor · çoktan
seçmeli") tek bir sözlükten gelir; her ekranda yeniden hatırlanmak zorunda kalan
bir etiket er geç ayrışır (Anayasa XI).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    BlueprintCell,
    ExamItem,
    ExamVersion,
    ExamVersionStatus,
    LearningOutcome,
    Question,
    QuestionDifficulty,
    QuestionPurpose,
    QuestionStatus,
    QuestionType,
)
from app.schemas.blueprint import (
    BlueprintCellIn,
    DistributionTargets,
    MissingCell,
    ReadinessOut,
    UnclassifiedItem,
)

# ---------------------------------------------------------------------------
# Ürün sözlüğü — etiketlerin TEK kaynağı
# ---------------------------------------------------------------------------

DIFFICULTY_TR: dict[QuestionDifficulty, str] = {
    QuestionDifficulty.EASY: "kolay",
    QuestionDifficulty.MEDIUM: "orta",
    QuestionDifficulty.HARD: "zor",
}

QUESTION_TYPE_TR: dict[QuestionType, str] = {
    QuestionType.MCQ: "çoktan seçmeli",
    QuestionType.OPEN: "açık uçlu",
    QuestionType.CODE_TRACE: "kod izleme",
    QuestionType.BUG_HUNT: "hata bulma",
}


def cell_label(
    outcome_code: str, difficulty: QuestionDifficulty, question_type: QuestionType
) -> str:
    """Hücrenin insan okunur adı. Hata ve rapor cümleleri bunu kullanır."""
    return f"{outcome_code} · {DIFFICULTY_TR[difficulty]} · {QUESTION_TYPE_TR[question_type]}"


# ---------------------------------------------------------------------------
# FR-112 — iç tutarlılık
# ---------------------------------------------------------------------------


def validate_distribution(
    cells: Sequence[BlueprintCellIn],
    *,
    outcome_codes: dict[UUID, str],
    targets: DistributionTargets | None,
) -> list[str]:
    """Kaydetmeden ÖNCE koşar. Boş liste = tutarlı.

    Döndürdüğü her cümle **hangi hücrenin ya da hangi marjinalin** tutmadığını
    söyler; "blueprint tutarsız" gibi karar verilemez bir metin üretmez. PostgreSQL
    kısıt ihlali bu cümleleri kuramazdı — kısıt adıyla döner (Anayasa V).

    Satır İÇİ olgular burada sınanmaz: adet ve puan aralığı pydantic'te, aynı
    hücrenin iki kez tanımlanamaması veritabanının UNIQUE'inde. Burada yalnız
    satırlar ARASI aritmetik var.
    """
    problems: list[str] = []

    # (a) Aynı hücre iki kez: DB de reddeder ama oradan gelen mesaj kısıt adıdır.
    seen: set[tuple[UUID, QuestionDifficulty, QuestionType]] = set()
    for cell in cells:
        key = (cell.learning_outcome_id, cell.difficulty, cell.question_type)
        if key in seen:
            label = cell_label(
                outcome_codes.get(cell.learning_outcome_id, "?"),
                cell.difficulty,
                cell.question_type,
            )
            problems.append(f"{label} hücresi iki kez tanımlanmış.")
        seen.add(key)

    # (b) Bilinmeyen öğrenme çıktısı: başka bir dersin çıktısı iliştirilemez.
    for cell in cells:
        if cell.learning_outcome_id not in outcome_codes:
            problems.append(
                f"{cell.learning_outcome_id} kimlikli öğrenme çıktısı bu derste yok; "
                "hücre bu çıktıya bağlanamaz."
            )

    if targets is None:
        return problems

    total = sum(cell.question_count for cell in cells)

    # (c) Toplam adet
    if targets.total_questions is not None and total != targets.total_questions:
        problems.append(
            f"Hücrelerin toplamı {total} soru ediyor ama sınav {targets.total_questions} "
            "soru olarak tanımlanmış."
        )

    # (d) Zorluk marjinali
    if targets.by_difficulty is not None:
        actual: dict[QuestionDifficulty, int] = {}
        for cell in cells:
            actual[cell.difficulty] = actual.get(cell.difficulty, 0) + cell.question_count
        for difficulty, expected in targets.by_difficulty.items():
            got = actual.get(difficulty, 0)
            if got != expected:
                problems.append(
                    f"{DIFFICULTY_TR[difficulty].capitalize()} sorular için {expected} "
                    f"istenmiş ama hücreler {got} tane veriyor."
                )

    # (e) Tip marjinali
    if targets.by_question_type is not None:
        actual_types: dict[QuestionType, int] = {}
        for cell in cells:
            actual_types[cell.question_type] = (
                actual_types.get(cell.question_type, 0) + cell.question_count
            )
        for question_type, expected in targets.by_question_type.items():
            got = actual_types.get(question_type, 0)
            if got != expected:
                problems.append(
                    f"{QUESTION_TYPE_TR[question_type].capitalize()} sorular için "
                    f"{expected} istenmiş ama hücreler {got} tane veriyor."
                )

    return problems


# ---------------------------------------------------------------------------
# FR-114 — yayın kapısı
# ---------------------------------------------------------------------------


async def readiness_report(
    session: AsyncSession,
    version: ExamVersion,
    *,
    cells: Sequence[BlueprintCell] | None = None,
) -> ReadinessOut:
    """Sürümün blueprint'ini karşılayıp karşılamadığını raporlar.

    İki liste döner ve **ikisi de** kapıyı kapatır:

    - `missing_cells` — istenen adet ile dolan adet tutmayan hücreler.
    - `unclassified_items` — sınıflandırması eksik, blueprint'te hücresi olmayan
      veya dondurulan puanı güncel hücre puanıyla uyuşmayan kalemler. Bunlar ayrı
      raporlanmasalardı başka bir hücre eksikmiş gibi görünürlerdi ve öğretmen
      yanlış hücreyi düzeltmeye çalışırdı (data-model.md §8 madde 7).

    Yalnız `approved` sorular sayılır: FR-119'un onay kapısı burada da geçerlidir,
    onaysız bir soru kâğıdı dolduramaz.
    """
    if cells is None:
        cells = list(
            (
                await session.execute(
                    select(BlueprintCell).where(BlueprintCell.blueprint_id == version.blueprint_id)
                )
            )
            .scalars()
            .all()
        )
    else:
        cells = list(cells)
    codes = await outcome_codes_of(session, [cell.learning_outcome_id for cell in cells])
    cell_by_key = {
        (cell.learning_outcome_id, cell.difficulty, cell.question_type): cell for cell in cells
    }

    rows = list(
        await session.execute(
            select(ExamItem.position, ExamItem.points, Question)
            .join(Question, Question.id == ExamItem.question_id)
            .where(ExamItem.exam_version_id == version.id)
            .order_by(ExamItem.position)
        )
    )

    filled: dict[tuple[UUID, QuestionDifficulty, QuestionType], int] = {}
    unclassified: list[UnclassifiedItem] = []

    for position, item_points, question in rows:
        missing_fields = [
            name
            for name, value in (
                ("learning_outcome", question.learning_outcome_id),
                ("difficulty", question.difficulty),
            )
            if value is None
        ]
        if missing_fields:
            eksikler = " ve ".join(
                "öğrenme çıktısı" if name == "learning_outcome" else "zorluk seviyesi"
                for name in missing_fields
            )
            unclassified.append(
                UnclassifiedItem(
                    question_id=question.id,
                    position=position,
                    missing_fields=missing_fields,
                    label=(
                        f"{position}. soru sınıflandırılmamış: {eksikler} atanmamış, "
                        "bu yüzden hiçbir hücreye sayılmıyor."
                    ),
                )
            )
            continue

        if question.purpose is not QuestionPurpose.ASSESSMENT:
            unclassified.append(
                UnclassifiedItem(
                    question_id=question.id,
                    position=position,
                    missing_fields=["purpose"],
                    label=(
                        f"{position}. soru prova amaçlı; resmî kâğıda yalnız assessment "
                        "amaçlı soru konulabilir."
                    ),
                )
            )
            continue

        if question.status is not QuestionStatus.APPROVED:
            # Onaysız soru hücreyi doldurmaz; eksik hücre olarak görünür.
            continue

        assert question.learning_outcome_id is not None
        assert question.difficulty is not None
        key = (question.learning_outcome_id, question.difficulty, question.type)
        cell = cell_by_key.get(key)
        if cell is None:
            unclassified.append(
                UnclassifiedItem(
                    question_id=question.id,
                    position=position,
                    missing_fields=["blueprint_cell"],
                    label=(
                        f"{position}. sorunun öğrenme çıktısı, zorluk ve tür birleşimi "
                        "blueprint'te tanımlı bir hücreye ait değil."
                    ),
                )
            )
            continue

        filled[key] = filled.get(key, 0) + 1
        if item_points != cell.points_per_question:
            unclassified.append(
                UnclassifiedItem(
                    question_id=question.id,
                    position=position,
                    missing_fields=["points"],
                    label=(
                        f"{position}. sorunun dondurulan puanı {item_points}; "
                        f"blueprint hücresi {cell.points_per_question} puan istiyor. "
                        "Kâğıdın soru listesini yeniden kaydedin."
                    ),
                )
            )

    missing: list[MissingCell] = []
    for cell in cells:
        key = (cell.learning_outcome_id, cell.difficulty, cell.question_type)
        got = filled.get(key, 0)
        if got == cell.question_count:
            continue
        label = cell_label(
            codes.get(cell.learning_outcome_id, "?"), cell.difficulty, cell.question_type
        )
        eylem = "eksik" if got < cell.question_count else "fazla"
        missing.append(
            MissingCell(
                learning_outcome_id=cell.learning_outcome_id,
                difficulty=cell.difficulty,
                question_type=cell.question_type,
                required=cell.question_count,
                filled=got,
                label=(
                    f"{label} hücresi {cell.question_count} soru istiyor, {got} tane var ({eylem})."
                ),
            )
        )

    ready = not missing and not unclassified
    return ReadinessOut(
        ready=ready,
        missing_cells=missing,
        unclassified_items=unclassified,
        message=_readiness_message(missing, unclassified),
    )


def _readiness_message(
    missing: Sequence[MissingCell], unclassified: Sequence[UnclassifiedItem]
) -> str:
    if not missing and not unclassified:
        return "Kâğıt blueprint'i birebir karşılıyor; sınav yayınlanabilir."
    parts: list[str] = []
    if missing:
        parts.append(f"{len(missing)} hücre blueprint'e uymuyor.")
    if unclassified:
        parts.append(f"{len(unclassified)} soru sınıflandırma, hücre veya puan bakımından uyumsuz.")
    parts.append("Sınav bu hâliyle yayınlanamaz.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# FR-115 — dondurma
# ---------------------------------------------------------------------------


def snapshot_of(cells: Sequence[BlueprintCell], codes: dict[UUID, str]) -> list[dict[str, Any]]:
    """Yayın anındaki dağılımı kanıt olarak dondurur.

    Kodu da yazar: `learning_outcomes.code` sonradan düzenlenebilir ve kanıt,
    okunduğu gün anlaşılabilir olmalı. Kimlik de durur ki bağ kaybolmasın.
    """
    return [
        {
            "learning_outcome_id": str(cell.learning_outcome_id),
            "learning_outcome_code": codes.get(cell.learning_outcome_id, "?"),
            "difficulty": cell.difficulty.value,
            "question_type": cell.question_type.value,
            "question_count": cell.question_count,
            "points_per_question": cell.points_per_question,
            "label": cell_label(
                codes.get(cell.learning_outcome_id, "?"), cell.difficulty, cell.question_type
            ),
        }
        for cell in sorted(
            cells,
            key=lambda cell: (
                codes.get(cell.learning_outcome_id, "?"),
                cell.difficulty.value,
                cell.question_type.value,
            ),
        )
    ]


async def outcome_codes_of(session: AsyncSession, outcome_ids: Sequence[UUID]) -> dict[UUID, str]:
    if not outcome_ids:
        return {}
    rows = await session.execute(
        select(LearningOutcome.id, LearningOutcome.code).where(
            LearningOutcome.id.in_(set(outcome_ids))
        )
    )
    return {row[0]: row[1] for row in rows}


async def published_version_of(session: AsyncSession, blueprint_id: UUID) -> ExamVersion | None:
    """Blueprint'in yayınlanmış sürümü. Kısmi tekil indeks en çok bir tane garantiler."""
    return await session.scalar(
        select(ExamVersion).where(
            ExamVersion.blueprint_id == blueprint_id,
            ExamVersion.status == ExamVersionStatus.PUBLISHED,
        )
    )


async def supersede_published(
    session: AsyncSession, blueprint_id: UUID, *, now: datetime
) -> ExamVersion | None:
    """Yayındaki sürümü `superseded` yapar ve onu döndürür.

    Yeni sürüm yayınlanmadan ÖNCE çağrılmalıdır: `exam_versions_one_published`
    kısmi tekil indeksi aynı anda iki yayınlanmış sürüme izin vermez.

    Yürüyen oturumlara DOKUNMAZ. `superseded` bir sürümün satırı da kalemleri de
    yerinde durur ve `exam_versions_read`'in üçüncü OR dalı oturum sahibine okumayı
    sürdürür — sınav ortasında kâğıt değişmez (data-model.md §8 madde 9).
    """
    current = await published_version_of(session, blueprint_id)
    if current is None:
        return None
    current.status = ExamVersionStatus.SUPERSEDED
    current.superseded_at = now
    await session.flush()
    return current
