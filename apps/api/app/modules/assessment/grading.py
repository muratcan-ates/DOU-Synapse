"""Puanlama — T031.

**KOD ASLA ÇALIŞTIRILMAZ.** `code_trace` ve `bug_hunt` dahil hiçbir değerlendirme
öğrenci kodunu ya da soru kodunu yürütmez: ne `exec`, ne `eval`, ne `subprocess`,
ne sandbox (FR-026). Değerlendirme tamamen cevap anahtarı ve kaynak chunk üzerinden
metinseldir. Bu, isteğe bağlı bir sadeleştirme değil, bilinçli bir güvenlik
kararıdır — kullanıcıdan gelen kodu çalıştıran bir uç, sızdırdığı her şeyi
sunucunun yetkileriyle sızdırır.

Üç ayrı yol var ve karıştırılmaz:

| Tip | Yol | LLM |
|---|---|---|
| `mcq` | cevap anahtarıyla karşılaştırma + çeldirici→kaynak eşlemesi | **hayır** |
| `open` + `short_answer` | kabul edilen karşılıklarla normalize eşleştirme | **hayır** |
| `open` + `essay`, `code_trace`, `bug_hunt` | rubrik + anahtar + kaynakla şemalı | evet |

LLM yolunda çıktı şemaya uymazsa **bir kez** yeniden denenir; yine uymazsa öğrenciye
uydurma puan gösterilmez, "değerlendirme tamamlanamadı" döner (FR-020). Değerlendirmenin
dayandığı `dayanak_chunk_id` set-membership kontrolünden geçer; geçmezse dayanak düşer
ama puan durur — kaynak uydurmak cevabı geçersiz kılmaz, yalnız kaynağı geçersiz kılar.

Dosya adı ve sayfa numarası her zaman **chunk metadata'sından** üretilir, model
metninden değil (Anayasa I).

Sonuç tipi neden `contracts.GradedAnswer` değil: o tip `score: int` taşır ve
"değerlendirme tamamlanamadı" durumunu ifade edemez — döndürebilmek için bir puan
uydurmak gerekirdi, ki FR-020 tam olarak bunu yasaklıyor. Bu yüzden buradaki
`GradingOutcome` bir üst kümedir (`graded`, `why_wrong_chunk_id`, `message`).
`contracts.py` tek taraflı değiştirilmez; gerekirse gruba yazılır
(bkz. docs/team/parallel/KARARLAR_SERIT4.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import text_tr
from app.core.errors import AppError
from app.core.llm_json import first_json_object
from app.core.logging import get_logger
from app.models.assessment import Question
from app.models.core import Chunk, Document
from app.modules.assessment.question_gen import (
    StructuredCompletion,
    resolve_completion,
)
from app.schemas.assessment import (
    AnswerFormat,
    BugHuntPayload,
    CodeTracePayload,
    McqPayload,
    OpenPayload,
    SourceRefOut,
    parse_payload,
)

logger = get_logger("app.assessment.grading")

SNIPPET_CHARS = 320


# ---------------------------------------------------------------------------
# Kaynak referansları
# ---------------------------------------------------------------------------


def chunk_location(chunk: Chunk) -> str:
    """'Sayfa 7' | 'Slayt 3' | bölüm adı. `contracts.RetrievedChunk.location` ile aynı kural."""
    if chunk.page_number is not None:
        return f"Sayfa {chunk.page_number}"
    if chunk.slide_number is not None:
        return f"Slayt {chunk.slide_number}"
    return chunk.section_title or "Konum yok"


def _best_snippet(text: str, focus: str | None) -> str:
    """Chunk'ın `focus` metniyle en çok örtüşen cümlesini kısaltarak döndürür.

    "Neden yanlış?" bütün chunk'ı basmak yerine çelişen cümleyi göstermelidir;
    seçim kelime örtüşmesiyle deterministiktir, modele sorulmaz.
    """
    condensed = " ".join(text.split())
    if not focus:
        return condensed[:SNIPPET_CHARS]

    needle = set(text_tr.tokens(focus))
    sentences = [part.strip() for part in condensed.replace("!", ".").split(".") if part.strip()]
    if not sentences:
        return condensed[:SNIPPET_CHARS]

    best = max(sentences, key=lambda part: len(needle & set(text_tr.tokens(part))))
    return best[:SNIPPET_CHARS]


@dataclass(frozen=True, slots=True)
class SourceMaterial:
    """Alıntı üretmek için gereken ham malzeme.

    Referanstan ayrı durur çünkü aynı chunk, farklı cevaplar için **farklı
    odaklarla** alıntılanır: bir sınavda iki öğrenci farklı çeldirici seçtiyse
    ikisine de kendi seçimiyle çelişen cümle gösterilmelidir. Malzeme bir kez
    toplu okunur, referanslar ondan üretilir — soru başına ayrı sorgu atılmaz.
    """

    chunk_id: UUID
    file_name: str
    location: str
    text: str

    def reference(self, *, focus: str | None = None) -> SourceRefOut:
        return SourceRefOut(
            chunk_id=self.chunk_id,
            file_name=self.file_name,
            location=self.location,
            snippet=_best_snippet(self.text, focus),
        )


async def load_source_material(
    session: AsyncSession, chunk_ids: Sequence[UUID]
) -> dict[UUID, SourceMaterial]:
    """Chunk kimliklerini tek sorguda kaynak malzemesine çevirir.

    Görünmeyen (başka dersin) bir chunk RLS yüzünden sonuçta yer almaz; çağıran
    eksik kimliği "kaynak gösterilemedi" olarak karşılar.
    """
    unique = list(dict.fromkeys(chunk_ids))
    if not unique:
        return {}
    rows = await session.execute(
        select(Chunk, Document.file_name)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(unique))
    )
    return {
        chunk.id: SourceMaterial(
            chunk_id=chunk.id,
            file_name=file_name,
            location=chunk_location(chunk),
            text=chunk.text,
        )
        for chunk, file_name in rows.all()
    }


async def load_source_refs(
    session: AsyncSession, chunk_ids: Sequence[UUID], *, focus: str | None = None
) -> dict[UUID, SourceRefOut]:
    """Tek odakla yetinen çağıranlar için kısayol (soru listesi, ipucu)."""
    material = await load_source_material(session, chunk_ids)
    return {chunk_id: item.reference(focus=focus) for chunk_id, item in material.items()}


# ---------------------------------------------------------------------------
# Sonuç
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GradingOutcome:
    """Tek bir cevabın değerlendirme sonucu.

    `graded=False` "cevap yanlış" DEĞİLDİR: "değerlendirme tamamlanamadı"dır. İkisi
    ayrı tutulur çünkü ilki puana 0 olarak girer, ikincisi puana hiç girmez.
    """

    graded: bool
    score: int | None = None
    is_correct: bool | None = None
    missing_points: list[str] = field(default_factory=list)
    #: MCQ'da seçilen çeldiricinin çeliştiği chunk (FR-021).
    why_wrong_chunk_id: UUID | None = None
    #: Açık uçluda değerlendirmenin dayandığı chunk.
    evidence_chunk_id: UUID | None = None
    message: str | None = None
    #: "Neden yanlış" alıntısını odaklamak için: öğrencinin seçtiği/yazdığı metin.
    focus: str | None = None


_UNGRADABLE_MESSAGE = (
    "Bu cevabın değerlendirmesi tamamlanamadı. Puanınıza katılmadı; eğitmeninize bildirebilirsiniz."
)


def _ungraded(reason: str) -> GradingOutcome:
    logger.warning("değerlendirme tamamlanamadı", extra={"context": {"reason": reason}})
    return GradingOutcome(graded=False, message=_UNGRADABLE_MESSAGE)


# ---------------------------------------------------------------------------
# MCQ — deterministik
# ---------------------------------------------------------------------------


def grade_mcq(payload: McqPayload, given: str) -> GradingOutcome:
    """Şık karşılaştırması. LLM yok, rastgelelik yok, ağ yok.

    Öğrencinin gönderdiği şık anahtarı büyük/küçük harf ve boşluk toleranslı
    okunur; tanınmayan bir şık 0 puan alır ve "neden yanlış" gösterilmez —
    gösterilecek bir çeldirici yoktur.
    """
    chosen = given.strip()
    keys = {option.key.strip().casefold(): option for option in payload.options}
    option = keys.get(chosen.casefold())
    if option is None:
        return GradingOutcome(
            graded=True,
            score=0,
            is_correct=False,
            message="Geçersiz şık gönderildi.",
        )

    if option.key == payload.answer_key:
        return GradingOutcome(graded=True, score=100, is_correct=True, focus=option.text)

    return GradingOutcome(
        graded=True,
        score=0,
        is_correct=False,
        why_wrong_chunk_id=payload.distractor_sources.get(option.key),
        focus=option.text,
    )


# ---------------------------------------------------------------------------
# Kısa cevap — deterministik
# ---------------------------------------------------------------------------


def grade_short_answer(
    payload: OpenPayload, given: str, *, source_chunk_id: UUID
) -> GradingOutcome:
    """Kabul edilen karşılıklarla normalize eşleştirme (Karar 4).

    Eşleşme kuralı: normalize edilmiş öğrenci cevabı, kabul edilen karşılıklardan
    birine eşitse ya da onu bir kelime sınırında içeriyorsa doğrudur. Kapsama izni
    "İşletim sistemi çekirdeği" gibi cümle içinde verilen doğru cevapları kurtarır;
    kelime sınırı şartı "ram" ile "program"ı birbirine karıştırmayı önler.

    `text_tr.normalize` AKSAN SÖKER: cevap anahtarı "çözüm" iken "cozum" yazan
    öğrenci puanını alır. Bu bilinçli bir ürün kararıdır ve bedeliyle birlikte
    o fonksiyonun docstring'inde yazılıdır — burada tekrarlanmıyor ki iki metin
    bir gün ayrışmasın.
    """
    answer = text_tr.normalize(given)
    if not answer:
        return GradingOutcome(graded=True, score=0, is_correct=False, focus=given)

    haystack = f" {answer} "
    for accepted in payload.accepted_answers:
        needle = text_tr.normalize(accepted)
        if needle and (answer == needle or f" {needle} " in haystack):
            return GradingOutcome(graded=True, score=100, is_correct=True, focus=given)

    return GradingOutcome(
        graded=True,
        score=0,
        is_correct=False,
        missing_points=[payload.answer_key],
        why_wrong_chunk_id=source_chunk_id,
        focus=given,
    )


# ---------------------------------------------------------------------------
# Açık uçlu / kod — şemalı LLM değerlendirmesi
# ---------------------------------------------------------------------------


class _LlmVerdict(BaseModel):
    """Modelden beklenen şema. Alan adları Türkçedir (03_ASSESSMENT_BRIEF)."""

    score: int = Field(ge=0, le=100)
    eksik_noktalar: list[str] = Field(default_factory=list, max_length=12)
    dayanak_chunk_id: UUID | None = None


_SYSTEM_PROMPT = (
    "Sen bir üniversite dersinin sınav kâğıdını okuyan asistansın. Öğrencinin "
    "cevabını, verilen cevap anahtarı ve kaynak bölümlere göre değerlendirirsin. "
    "Kaynakta olmayan bir bilgiyi eksiklik saymazsın. Cevabın SADECE JSON olmalı: "
    '{"score": 0-100, "eksik_noktalar": ["..."], "dayanak_chunk_id": "<chunk_id>"}. '
    "Açıklama, markdown ya da ek metin yazma. eksik_noktalar Türkçedir. "
    "KOD ÇALIŞTIRMA; yalnız metin olarak karşılaştır."
)


def _reference_block(payload: BaseModel) -> str:
    """Değerlendirmenin dayanacağı anahtar/rubrik/ölçütler."""
    lines: list[str] = []
    if isinstance(payload, OpenPayload):
        lines.append(f"Soru: {payload.prompt}")
        lines.append(f"Cevap anahtarı: {payload.answer_key}")
        if payload.key_points:
            lines.append("Bulunması gereken noktalar:")
            lines += [f"- {point}" for point in payload.key_points]
        if payload.rubric:
            lines.append("Rubrik (ağırlıklar 100 üzerinden):")
            lines += [f"- {item.point} ({item.weight})" for item in payload.rubric]
    elif isinstance(payload, CodeTracePayload):
        lines.append(f"Soru: {payload.prompt}")
        lines.append(f"Kod:\n{payload.code}")
        lines.append(f"Beklenen çıktı: {payload.answer_key}")
    elif isinstance(payload, BugHuntPayload):
        lines.append(f"Soru: {payload.prompt}")
        lines.append(f"Kod:\n{payload.code}")
        lines.append(
            "Beklenen tespit: "
            f"satır {payload.answer_key.line}, tür '{payload.answer_key.bug_type}', "
            f"düzeltme: {payload.answer_key.fix_summary}"
        )
    return "\n".join(lines)


def _sources_block(refs: Sequence[tuple[UUID, str]]) -> str:
    return "\n\n".join(f"chunk_id: {chunk_id}\n{text}" for chunk_id, text in refs)


def _parse_verdict(raw: str) -> _LlmVerdict | None:
    """Ham yanıtı şemaya çevirir; uymuyorsa None (çağıran yeniden dener).

    Gürültü temizleme kuralı `core.llm_json` ile ortaktır: üretim, soru üretimi ve
    değerlendirme aynı sağlayıcıdan aynı gürültüyü alır, üç farklı temizleme
    kuralı sessiz tutarsızlık üretirdi (Anayasa XI).
    """
    data = first_json_object(raw)
    if data is None:
        return None
    try:
        return _LlmVerdict.model_validate(data)
    except ValidationError:
        return None


async def grade_with_llm(
    completion: StructuredCompletion,
    *,
    payload: BaseModel,
    given: str,
    sources: Sequence[tuple[UUID, str]],
) -> GradingOutcome:
    """Rubrik + cevap anahtarı + kaynak parçalarla şemalı değerlendirme.

    Şema bozuksa bir kez yeniden denenir; yine bozuksa uydurma puan gösterilmez.
    `dayanak_chunk_id` verilen kaynak kümesinde değilse yalnız dayanak düşer.
    """
    valid_ids = {chunk_id for chunk_id, _ in sources}
    user_prompt = "\n\n".join(
        [
            _reference_block(payload),
            f"Öğrencinin cevabı:\n{given}",
            "--- KAYNAK BÖLÜMLER ---",
            _sources_block(sources),
            "dayanak_chunk_id yukarıdaki kimliklerden biri olmalı.",
        ]
    )

    for attempt in range(2):
        try:
            raw = await completion.complete(system=_SYSTEM_PROMPT, user=user_prompt)
        except Exception:  # sağlayıcı hatası değerlendirmeyi düşürür, isteği patlatmaz
            logger.exception("değerlendirmede sağlayıcı hatası")
            continue

        verdict = _parse_verdict(raw)
        if verdict is None:
            logger.info("değerlendirme şeması bozuk", extra={"context": {"attempt": attempt + 1}})
            continue

        evidence = verdict.dayanak_chunk_id
        if evidence is not None and evidence not in valid_ids:
            # Uydurulmuş dayanak: puan durur, kaynak düşer (Anayasa I).
            logger.info("değerlendirme dayanağı set-membership'ten geçmedi")
            evidence = None

        return GradingOutcome(
            graded=True,
            score=verdict.score,
            is_correct=verdict.score >= 50,
            missing_points=verdict.eksik_noktalar,
            evidence_chunk_id=evidence,
            focus=given,
        )

    return _ungraded("şema iki denemede de tutmadı")


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------


async def grade_answer(
    session: AsyncSession,
    question: Question,
    given: str,
    *,
    completion: StructuredCompletion | None = None,
) -> GradingOutcome:
    """Bir cevabı tipine uygun yolla değerlendirir.

    Sağlayıcı **yalnız LLM gerektiren tipler için** ve ancak o noktaya gelindiğinde
    çözümlenir. Bu sıralama bilinçli: `mcq` ve `short_answer` deterministiktir ve
    sağlayıcı hiç kurulamıyorken bile puanlanmalıdır — sınavın çekirdeği LLM'in
    ayakta olmasına bağlı olmamalı.

    Sağlayıcı kurulamazsa istek 503'e dönmez; o cevap "değerlendirilemedi" olur
    (FR-020). Sınavın ortasında bir sağlayıcı arızası, öğrencinin diğer cevaplarını
    da düşürmemelidir.
    """
    try:
        payload = parse_payload(question.type, question.payload)
    except ValidationError:
        # Havuzdaki payload bozulmuş: onaylanmış bir soru okunamıyorsa öğrenciye
        # tahmin edilmiş bir puan vermektense değerlendirmeyi tamamlamamak yeğdir.
        return _ungraded("havuzdaki payload şemadan geçmedi")

    if isinstance(payload, McqPayload):
        return grade_mcq(payload, given)

    if isinstance(payload, OpenPayload) and payload.format is AnswerFormat.SHORT_ANSWER:
        return grade_short_answer(payload, given, source_chunk_id=question.source_chunk_id)

    if completion is None:
        try:
            completion = resolve_completion()
        except AppError:
            return _ungraded("LLM sağlayıcısı kurulamadı")

    chunk = await session.get(Chunk, question.source_chunk_id)
    if chunk is None:
        return _ungraded("sorunun kaynak parçası okunamadı")

    return await grade_with_llm(
        completion,
        payload=payload,
        given=given,
        sources=[(chunk.id, chunk.text)],
    )


def score_of(outcomes: Sequence[GradingOutcome]) -> float | None:
    """Cevaplanan soruların ortalaması.

    Değerlendirilememiş cevaplar (`graded=False`) paydaya da girmez: puanı hem
    düşürmezler hem şişirmezler. Hiç değerlendirilmiş cevap yoksa None döner —
    0 döndürmek "her şeyi yanlış yaptın" demekle aynı şeydir ve yanlıştır.
    """
    scores = [outcome.score for outcome in outcomes if outcome.graded and outcome.score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)
