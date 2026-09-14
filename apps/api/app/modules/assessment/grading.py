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
| `open` + `essay` | kaynaklı rubrik + yanlış/eksik yanıta alıntı ve sonraki ipucu | evet |
| `code_trace`, `bug_hunt` | deterministik çıktı/satır karşılaştırması | yalnız açıklama |

LLM yolunda çıktı şemaya uymazsa veya okunabilir kaynaklara dayanmıyorsa **bir kez**
yeniden denenir. İkinci deneme de doğrulanamazsa puan ve model geri bildirimi
gösterilmez; "değerlendirme tamamlanamadı" döner (FR-020). `dayanak_chunk_id`, modele
verilen okunabilir kaynak kümesinde olmalıdır. Kaynak yoksa sağlayıcı çağrılmaz.

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
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import text_tr
from app.core.errors import AppError
from app.core.llm_json import first_json_object
from app.core.logging import get_logger
from app.models.assessment import Question
from app.models.core import Chunk, Document
from app.modules.assessment.code_oracle import code_oracle
from app.modules.assessment.question_gen import (
    StructuredCompletion,
    resolve_grading_completion,
)
from app.schemas.assessment import (
    AnswerFormat,
    BugHuntPayload,
    CodeTracePayload,
    GroundedCriterionEvidence,
    GroundedFeedbackEvidence,
    McqPayload,
    OpenPayload,
    RubricCriterionScore,
    RubricItem,
    SourceRefOut,
    normalized_rubric,
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
    course_id: UUID | None = None

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

    RLS görünürlüğüne ek olarak chunk ile belgenin ders kimlikleri eşleşir.
    İki derse üye aktörde de bozuk çapraz belge bağı kaynak sayılmaz; çağıran
    eksik kimliği "kaynak gösterilemedi" olarak karşılar.
    """
    unique = list(dict.fromkeys(chunk_ids))
    if not unique:
        return {}
    rows = await session.execute(
        select(Chunk, Document.file_name)
        .join(
            Document,
            and_(Document.id == Chunk.document_id, Document.course_id == Chunk.course_id),
        )
        .where(Chunk.id.in_(unique))
    )
    return {
        chunk.id: SourceMaterial(
            chunk_id=chunk.id,
            file_name=file_name,
            location=chunk_location(chunk),
            text=chunk.text,
            course_id=chunk.course_id,
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
    #: Rubriğe bağlı sorularda ölçüt kırılımı (FR-117). Toplam puan bu satırlardan
    #: türetilir; model ayrı bir toplam verse bile o okunmaz.
    rubric_breakdown: list[RubricCriterionScore] = field(default_factory=list)
    grounded_missing_criterion: GroundedCriterionEvidence | None = None
    grounded_feedback: GroundedFeedbackEvidence | None = None
    feedback_version: Literal[1] | None = None


_UNGRADABLE_MESSAGE = (
    "Bu cevabın değerlendirmesi tamamlanamadı. Puanınıza katılmadı; eğitmeninize bildirebilirsiniz."
)


def _ungraded(reason: str) -> GradingOutcome:
    logger.warning("değerlendirme tamamlanamadı", extra={"context": {"reason": reason}})
    return GradingOutcome(graded=False, message=_UNGRADABLE_MESSAGE)


def _ungraded_new(reason: str) -> GradingOutcome:
    outcome = _ungraded(reason)
    outcome.feedback_version = 1
    return outcome


def grounded_feedback_is_valid(claim: GroundedFeedbackEvidence, *, source_text: str) -> bool:
    """Alıntının birebir üyeliğini sınar; pedagojik anlam doğruluğu iddiası taşımaz."""
    return bool(
        source_text.strip()
        and claim.quote.strip()
        and len(claim.quote) <= SNIPPET_CHARS
        and claim.quote in source_text
        and claim.next_hint.strip()
        and len(claim.next_hint) <= 1000
    )


def literal_feedback_quote(source_text: str) -> str:
    """Kaynağın ilk dolu cümlesinden gerçek bir kesit; whitespace uydurulmaz."""
    excerpt = source_text.lstrip()[:SNIPPET_CHARS]
    boundaries = [excerpt.find(mark) for mark in (".", "!", "?", "\n")]
    endings = [index for index in boundaries if index >= 0]
    if endings:
        excerpt = excerpt[: min(endings) + 1]
    return excerpt.rstrip()


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
    payload: OpenPayload, given: str, *, source_chunk_id: UUID, source_text: str | None = None
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
    if source_text is None or not source_text.strip():
        return _ungraded_new("kısa cevap kaynağı okunamadı")
    answer = text_tr.normalize(given)

    haystack = f" {answer} "
    for accepted in payload.accepted_answers:
        needle = text_tr.normalize(accepted)
        if needle and (answer == needle or f" {needle} " in haystack):
            return GradingOutcome(
                graded=True,
                score=100,
                is_correct=True,
                focus=given,
                evidence_chunk_id=source_chunk_id,
                feedback_version=1,
            )

    feedback = GroundedFeedbackEvidence(
        chunk_id=source_chunk_id,
        quote=literal_feedback_quote(source_text),
        next_hint=(
            "Kaynak cümlesindeki tanımı yanıtınla karşılaştır; farklı kalan kavramı yeniden yaz."
        ),
    )
    return GradingOutcome(
        graded=True,
        score=0,
        is_correct=False,
        missing_points=[payload.answer_key],
        why_wrong_chunk_id=source_chunk_id,
        evidence_chunk_id=source_chunk_id,
        focus=given,
        grounded_feedback=feedback,
        feedback_version=1,
    )


# ---------------------------------------------------------------------------
# Açık uçlu / kod — şemalı LLM değerlendirmesi
# ---------------------------------------------------------------------------


class _RubrikSatiri(BaseModel):
    """Modelin tek bir ölçüt için verdiği puan. Ağırlığı model DEĞİL biz biliriz."""

    olcut: str = Field(min_length=1, max_length=500)
    puan: int = Field(ge=0, le=100)


class _LlmVerdict(BaseModel):
    """Modelden beklenen şema. Alan adları Türkçedir (03_ASSESSMENT_BRIEF)."""

    score: int = Field(ge=0, le=100)
    eksik_noktalar: list[str] = Field(default_factory=list, max_length=12)
    dayanak_chunk_id: UUID | None = None
    #: Rubrik verilmişse ölçüt başına puan. Toplamı biz hesaplarız (FR-117).
    rubrik: list[_RubrikSatiri] = Field(default_factory=list, max_length=12)
    grounded_missing_criterion: GroundedCriterionEvidence | None = None
    grounded_feedback: GroundedFeedbackEvidence | None = None


_SYSTEM_PROMPT = (
    "Sen bir üniversite dersinin sınav kâğıdını okuyan asistansın. Öğrencinin "
    "cevabını, verilen cevap anahtarı ve kaynak bölümlere göre değerlendirirsin. "
    "Kaynakta olmayan bir bilgiyi eksiklik saymazsın. Cevabın SADECE JSON olmalı: "
    '{"score": 0-100, "eksik_noktalar": ["..."], "dayanak_chunk_id": "<chunk_id>"}. '
    "Açıklama, markdown ya da ek metin yazma. eksik_noktalar Türkçedir. "
    "KOD ÇALIŞTIRMA; yalnız metin olarak karşılaştır. "
    "Rubrik verilmişse her ölçüt için ayrıca "
    '"rubrik": [{"olcut": "<ölçütün metni>", "puan": 0-100} ...] yaz; ölçüt metnini '
    "verildiği gibi kopyala ve AĞIRLIKLARLA ÇARPMA — ağırlığı biz uygularız. "
    "Açıkça puanladığın bir rubrik ölçütü 100'ün altındaysa ve kaynakta bu ölçütle "
    "ilgili gerçek bir alıntı varsa isteğe bağlı grounded_missing_criterion ver: "
    '{"criterion":"<rubrikteki ölçütün birebir metni>","chunk_id":"<dayanak_chunk_id>",'
    '"quote":"<kaynağın birebir, boş olmayan en fazla 320 karakterlik kesiti>"}. '
    "Bu alanı kaynaksız doldurma, alıntıyı yeniden yazma; uygun alıntı veya puanlanmış "
    "ölçüt yoksa null ver. Alıntı bir anlam doğrulama sertifikası değildir. "
    "Toplam puan 100 altındaysa grounded_feedback zorunludur: "
    '{"chunk_id":"<dayanak_chunk_id>","quote":"<kaynağın birebir <=320 karakter kesiti>",'
    '"next_hint":"<yanıt sonrası Türkçe çalışma adımı; boş olmayan <=1000 karakter>"}. '
    "Kaynaksız iddia veya yeniden yazılmış alıntı verme."
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
    rubric = payload_rubric(payload) if isinstance(payload, OpenPayload) else []
    if rubric:
        lines.append("Rubrik (ağırlıklar 100 üzerinden):")
        lines += [f"- {item.point} ({item.weight:.4g})" for item in normalized_rubric(rubric)]
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


def payload_rubric(payload: BaseModel) -> list[RubricItem]:
    return (
        payload.rubric
        if isinstance(payload, (OpenPayload, CodeTracePayload, BugHuntPayload))
        else []
    )


def grounded_criterion_is_valid(
    claim: GroundedCriterionEvidence,
    *,
    rubric: list[RubricItem],
    breakdown: list[RubricCriterionScore],
    source_text: str,
) -> bool:
    """Ölçütün kimliğini, puanlanan eksikliği ve birebir kaynak alıntısını doğrular.

    Bu kontroller kaynak ve ölçüt bağlantısını doğrular. Modelin pedagojik
    yorumunun anlamsal doğruluğunu ölçmez. Hiçbir kod çalıştırılmaz.
    """
    names = [text_tr.fold(item.point.strip()) for item in rubric]
    if not rubric or not all(names) or len(set(names)) != len(names):
        return False
    matching = [item for item in normalized_rubric(rubric) if item.point == claim.criterion]
    scored = [row for row in breakdown if row.point == claim.criterion]
    if len(matching) != 1 or len(scored) != 1:
        return False
    criterion, row = matching[0], scored[0]
    return bool(
        row.score < 100
        and row.weight == criterion.weight
        and row.earned == round(row.weight * row.score / 100)
        and claim.quote.strip()
        and source_text.strip()
        and claim.quote in source_text
    )


def _rubric_breakdown(payload: BaseModel, verdict: _LlmVerdict) -> list[RubricCriterionScore]:
    """Ölçüt puanlarını normalize edilmiş ağırlıklarla birleştirir.

    İki "boş" durumu birbirinden AYRI tutulur ve ayrımı karıştırmak pahalıydı:

    - **Sorunun rubriği yok** → kırılım da yok, çağıran modelin `score`'unu kullanır.
    - **Model hiç kırılım döndürmedi** (eski sağlayıcı, sahte sağlayıcı, ya da
      talimatı yok sayan bir yanıt) → yine kırılım yok. Bu dal olmadan bütün
      ölçütler 0 puanla girer ve gerçekten 75 alan bir cevap SESSİZCE 0'a düşerdi.
      İlk yazımda bu dal yoktu ve dört değerlendirme testi bunu yakaladı; kusurun
      sınıfı `data-model.md` §2.15'in uyardığı "sessizce değerlendirilemez hâle
      gelme" sınıfıdır.
    - **Model KISMİ kırılım döndürdü** → atlanan ölçüt 0 puanla girer. Burada
      fail-closed doğrudur: cevaplanmamış bir kriteri karşılanmış saymak, puanı
      şişirmek olurdu (Anayasa IV).
    """
    rubric = payload_rubric(payload)
    if not rubric:
        return []
    if not verdict.rubrik:
        return []

    # Eşleme Türkçe'ye göre katlanır: str.casefold() "ADIMLARI"yı "adimlari",
    # "Adımları"yı "adımları" yapar ve aynı ölçüt eşleşmez — 100 alan cevap 0'a
    # düşer (L8 bulgusu, 14 Eylül 2026). text_tr.fold iki yazımı da aynı anahtara indirger.
    puanlar = {text_tr.fold(row.olcut.strip()): row.puan for row in verdict.rubrik}
    normalized = normalized_rubric(rubric)
    if not any(text_tr.fold(item.point.strip()) in puanlar for item in normalized):
        # Model kırılım döndürdü ama HİÇBİR satır rubrikle eşleşmiyor: bu "kısmi
        # kırılım" değil, başka bir adlandırmadır. Hepsini 0'la doldurmak doğru
        # cevabı sessizce sıfırlar; "kırılım yok" gibi davranılır ve çağıran
        # modelin toplam score'unu kullanır (yukarıdaki ikinci boş durum).
        return []
    satirlar: list[RubricCriterionScore] = []
    for item in normalized:
        puan = puanlar.get(text_tr.fold(item.point.strip()), 0)
        satirlar.append(
            RubricCriterionScore(
                point=item.point,
                weight=item.weight,
                score=puan,
                earned=round(item.weight * puan / 100),
            )
        )
    return satirlar


class _CodeExplanation(BaseModel):
    dayanak_chunk_id: UUID
    grounded_feedback: GroundedFeedbackEvidence


_CODE_EXPLANATION_PROMPT = (
    "Kod yanıtının doğru/yanlış kararı metinsel cevap anahtarıyla sunucu tarafından verildi. "
    "PUAN VERME, rubrik üretme; kod çalıştırma. Yalnız yanlış yanıtı kaynakla karşılaştırmaya "
    "yardım eden Türkçe sonraki adımı ver. Cevabın yalnız JSON olsun: "
    '{"dayanak_chunk_id":"<verilen kaynak>","grounded_feedback":'
    '{"chunk_id":"<aynı kaynak>","quote":"<kaynağın birebir, boş olmayan <=320 karakter kesiti>",'
    '"next_hint":"<boş olmayan <=1000 karakter sonraki çalışma adımı>"}}. '
    "Alıntıyı yeniden yazma ve verilen kaynak dışında bilgi kullanma."
)


def _correct_code(source_id: UUID, given: str) -> GradingOutcome:
    return GradingOutcome(
        graded=True,
        score=100,
        is_correct=True,
        evidence_chunk_id=source_id,
        focus=given,
        feedback_version=1,
    )


async def _grade_code(
    completion: StructuredCompletion,
    *,
    payload: CodeTracePayload | BugHuntPayload,
    given: str,
    sources: Sequence[tuple[UUID, str]],
) -> GradingOutcome:
    score = code_oracle(payload, given)
    if score is None:
        return _ungraded_new("kod yanıtı deterministik karşılaştırma için belirsiz")
    if score == 100:
        return _correct_code(sources[0][0], given)
    source_texts = dict(sources)
    user = "\n\n".join(
        [
            _reference_block(payload),
            f"Öğrencinin cevabı:\n{given}",
            "Sunucunun deterministik kararı: yanlış (0).",
            _sources_block(sources),
        ]
    )
    for _ in range(2):
        try:
            raw = await completion.complete(system=_CODE_EXPLANATION_PROMPT, user=user)
            data = first_json_object(raw)
            verdict = _CodeExplanation.model_validate(data)
        except Exception:
            logger.info("kod açıklaması şema veya sağlayıcı denetiminden geçmedi")
            continue
        claim = verdict.grounded_feedback
        if claim.chunk_id != verdict.dayanak_chunk_id or not grounded_feedback_is_valid(
            claim, source_text=source_texts.get(claim.chunk_id, "")
        ):
            continue
        return GradingOutcome(
            graded=True,
            score=0,
            is_correct=False,
            why_wrong_chunk_id=claim.chunk_id,
            evidence_chunk_id=claim.chunk_id,
            focus=given,
            grounded_feedback=claim,
            feedback_version=1,
        )
    return _ungraded_new("kod açıklaması iki denemede kaynak ve ipucuyla doğrulanamadı")


async def grade_with_llm(
    completion: StructuredCompletion,
    *,
    payload: BaseModel,
    given: str,
    sources: Sequence[tuple[UUID, str]],
) -> GradingOutcome:
    """Rubrik + cevap anahtarı + kaynak parçalarla şemalı değerlendirme.

    Şema ve kaynak hataları aynı iki deneme bütçesini paylaşır. Geçerli dayanak
    olmadan puan veya modelin eksik nokta iddiaları gösterilmez. Bu kontrol kaynak
    kimliğini doğrular; değerlendirme ile kaynak arasındaki anlamı ölçmez.
    """
    readable_sources = [(chunk_id, body) for chunk_id, body in sources if body.strip()]
    if not readable_sources:
        return _ungraded_new("okunabilir kaynak parçası yok")
    if isinstance(payload, (CodeTracePayload, BugHuntPayload)):
        return await _grade_code(completion, payload=payload, given=given, sources=readable_sources)
    if isinstance(payload, OpenPayload) and payload.format is AnswerFormat.SHORT_ANSWER:
        return grade_short_answer(
            payload,
            given,
            source_chunk_id=readable_sources[0][0],
            source_text=readable_sources[0][1],
        )
    valid_ids = {chunk_id for chunk_id, _ in readable_sources}
    user_prompt = "\n\n".join(
        [
            _reference_block(payload),
            f"Öğrencinin cevabı:\n{given}",
            "--- KAYNAK BÖLÜMLER ---",
            _sources_block(readable_sources),
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
        if evidence not in valid_ids:
            logger.info("değerlendirme dayanağı set-membership'ten geçmedi")
            continue

        breakdown = _rubric_breakdown(payload, verdict)
        grounded = verdict.grounded_missing_criterion
        if grounded is not None:
            explicit = [
                row
                for row in verdict.rubrik
                if text_tr.fold(row.olcut.strip()) == text_tr.fold(grounded.criterion.strip())
            ]
            if (
                grounded.chunk_id != evidence
                or len(explicit) != 1
                or explicit[0].olcut != grounded.criterion
                or not grounded_criterion_is_valid(
                    grounded,
                    rubric=payload_rubric(payload),
                    breakdown=breakdown,
                    source_text=dict(readable_sources).get(grounded.chunk_id, ""),
                )
            ):
                logger.info("eksik ölçüt açıklaması kaynak ve ölçüt doğrulamasından geçmedi")
                continue
        # FR-117: rubrik varsa toplam KIRILIMDAN türetilir. Model kendi `score`'unu
        # da verir ama okunmaz — ikisi çelişirse öğrenciye gösterilen tablonun
        # toplamı tutmazdı (Anayasa III).
        score = sum(row.earned for row in breakdown) if breakdown else verdict.score
        feedback = verdict.grounded_feedback
        if score < 100 and feedback is None:
            continue
        if feedback is not None and (
            feedback.chunk_id != evidence
            or not grounded_feedback_is_valid(
                feedback, source_text=dict(readable_sources).get(feedback.chunk_id, "")
            )
        ):
            continue

        return GradingOutcome(
            graded=True,
            score=score,
            is_correct=score >= 50,
            missing_points=verdict.eksik_noktalar,
            evidence_chunk_id=evidence,
            focus=given,
            rubric_breakdown=breakdown,
            grounded_missing_criterion=grounded,
            why_wrong_chunk_id=feedback.chunk_id if feedback is not None and score < 100 else None,
            grounded_feedback=feedback,
            feedback_version=1,
        )

    return _ungraded_new("değerlendirme iki denemede de doğrulanamadı")


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

    material = await load_source_material(session, [question.source_chunk_id])
    source = material.get(question.source_chunk_id)
    if source is None or source.course_id != question.course_id or not source.text.strip():
        return _ungraded_new("sorunun aynı ders içindeki kaynak ve belgesi okunamadı")
    if isinstance(payload, OpenPayload) and payload.format is AnswerFormat.SHORT_ANSWER:
        return grade_short_answer(
            payload, given, source_chunk_id=source.chunk_id, source_text=source.text
        )
    if isinstance(payload, (CodeTracePayload, BugHuntPayload)):
        score = code_oracle(payload, given)
        if score is None:
            return _ungraded_new("kod yanıtı deterministik karşılaştırma için belirsiz")
        if score == 100:
            return _correct_code(source.chunk_id, given)

    if completion is None:
        try:
            completion = resolve_grading_completion(
                payload=payload, given=given, sources=[(source.chunk_id, source.text)]
            )
        except AppError:
            return _ungraded_new("LLM sağlayıcısı kurulamadı")

    return await grade_with_llm(
        completion,
        payload=payload,
        given=given,
        sources=[(source.chunk_id, source.text)],
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
