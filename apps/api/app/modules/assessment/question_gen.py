"""Soru üretimi — T029.

Ders materyalinden dört tipte soru üretir: `mcq`, `open` (klasik/kısa cevap),
`code_trace`, `bug_hunt`. Akış tek yönlüdür ve her adımı fail-closed'dır:

    konu adı → retrieval → prompt → LLM → Pydantic doğrulama → kaynak
    doğrulaması → havuza `status=draft` yazım

**Üretilen hiçbir soru öğrenciye görünmez.** Bu modülde `approved` yazan bir kod
yolu yoktur; onay yalnız `api/questions.py`'deki eğitmen ucundan gelir (FR-023).

İki deterministik kural, modelin uydurmasını yapısal olarak imkânsız kılar:

1. **`source_chunk_id` set-membership'ten geçer.** Model retrieve edilmemiş bir
   kimlik yazarsa soru havuza *hiç* yazılmaz — düzeltilmez, atılır (Anayasa I).
2. **`distractor_sources` modelden istenmez.** Her yanlış şıkkın çeliştiği bölüm,
   şık metni ile retrieve edilmiş chunk'lar arasında kelime örtüşmesiyle
   *bizim tarafımızdan* eşleştirilir. Modelden istenseydi uydurulabilirdi;
   deterministik yol her zaman birincildir (03_ASSESSMENT_BRIEF, Teslimat 4).

Şemaya uymayan çıktı bir kez yeniden denenir (FR-020/SC-009); ikinci turda da
uymayan sorular sessizce düşer, geçerli olanlar yazılır ve kaçının düştüğü
`GenerationReport` ile geri döner — şema geçerliliği ölçülebilsin diye (Anayasa III).

Bağımlılık notu: LLM erişimi için `contracts.Generator` KULLANILAMAZ; o protokol
bir sohbet cevabı (`GeneratedAnswer`) üretir, burada gereken ise şemalı JSON'dur.
Bu yüzden aşağıda dar bir `StructuredCompletion` protokolü ve Şerit 2'nin
`LlmClient`'ını ona çeviren küçük bir adaptör var. Retrieval tarafında sapma yok:
`contracts.Retriever` doğrudan kullanılıyor.

Sağlayıcılar `resolve_retriever` / `resolve_completion` ile çözümlenir: testlerin
bağladığı sahteler varsa onlar, yoksa gerçek modüller. Hiçbir sağlayıcı kurulamazsa
üretim ucu 503 döner — soru uydurulmaz (KARARLAR_SERIT4.md §3).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import RetrievedChunk, Retriever
from app.core.logging import get_logger
from app.models.assessment import (
    LearningOutcome,
    Question,
    QuestionDifficulty,
    QuestionStatus,
    QuestionType,
    Topic,
)
from app.modules.generation.llm import LlmRequest, build_llm_client
from app.modules.retrieval.service import HybridRetriever
from app.schemas.assessment import (
    AnswerFormat,
    BugHuntAnswerKey,
    McqOption,
    RubricItem,
    parse_payload,
)

logger = get_logger("app.assessment.question_gen")


# ---------------------------------------------------------------------------
# LLM yüzeyi
# ---------------------------------------------------------------------------


class StructuredCompletion(Protocol):
    """Şemalı JSON isteyen çağrıların tek yüzeyi.

    Ham metin döner; doğrulama **çağırana** aittir. Sağlayıcının JSON modu olsun
    ya da olmasın bu imza değişmez, dolayısıyla sahte sağlayıcı ile gerçeği
    testte birbirinin yerine koymak mümkündür.
    """

    async def complete(self, *, system: str, user: str) -> str: ...


#: Retrieval oturuma bağlıdır (`HybridRetriever(session)`), yani süreç ömürlü tek
#: bir nesne olamaz; kayıt bir fabrika tutar.
type RetrieverFactory = Callable[[AsyncSession], Retriever]


class _GenerationCompletion:
    """Üretim servisinin `LlmClient`'ını `StructuredCompletion` yüzeyine çevirir.

    İki protokol de "system + user ver, metin al" diyor; aradaki tek fark
    `LlmRequest` zarfı. Adaptör burada duruyor çünkü `app/modules/generation/`
    başka bir şeridin dosyası ve oraya Şerit 4 kod yazmaz.
    """

    def __init__(self, client: Any, request_cls: Any) -> None:
        self._client = client
        self._request_cls = request_cls

    async def complete(self, *, system: str, user: str) -> str:
        completion = await self._client.complete(
            self._request_cls(system=system, user=user, json_output=True)
        )
        return str(completion.text)


#: Süreç ömrü boyunca geçerli sağlayıcı kaydı. Bir DI konteyneri değil, tek
#: kancadır: testler sahte uygulamalarla doldurur, üretimde boş kalır ve aşağıdaki
#: çözümleyiciler gerçek modülleri bulur.
_retriever_factory: RetrieverFactory | None = None
_completion: StructuredCompletion | None = None


def set_providers(
    *,
    retriever_factory: RetrieverFactory | None = None,
    completion: StructuredCompletion | None = None,
) -> None:
    """Sağlayıcıları bağlar. `None` geçilen sağlayıcı olduğu gibi bırakılır."""
    global _retriever_factory, _completion
    if retriever_factory is not None:
        _retriever_factory = retriever_factory
    if completion is not None:
        _completion = completion


def reset_providers() -> None:
    global _retriever_factory, _completion
    _retriever_factory = _completion = None


def resolve_retriever(session: AsyncSession) -> Retriever:
    """Kayıtlı fabrika varsa ondan, yoksa gerçek hibrit retrieval'dan."""
    if _retriever_factory is not None:
        return _retriever_factory(session)
    return HybridRetriever(session)


def resolve_completion() -> StructuredCompletion:
    """Kayıtlı sahte varsa ondan, yoksa üretim LLM istemcisinden.

    Sağlayıcı hiç kurulamıyorsa `build_llm_client()` `LlmUnavailableError` (503)
    fırlatır — yerelde ve CI'da anahtar yokken deterministik sahteye düşer.
    Buradan `None` DÖNMEZ; "sağlayıcı yok" durumu bir istisnadır, sessiz bir
    değer değil.
    """
    if _completion is not None:
        return _completion
    return _GenerationCompletion(build_llm_client(), LlmRequest)


# ---------------------------------------------------------------------------
# Metin yardımcıları
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"\w+", re.UNICODE)

#: Türkçe küçültme. `str.lower()` "İ" için birleşik nokta üretir, `upper()` ise
#: "i"yi "I" yapıp anlamı bozar (Anayasa V). Bu yüzden iki harf önce elle eşlenir.
_TR_LOWER = str.maketrans({"İ": "i", "I": "ı"})

#: Örtüşme skorunda ayırt ediciliği olmayan sık kelimeler.
_STOPWORDS = frozenset(
    """
    ve veya ile ama fakat çünkü ki de da mi mı mu mü bir bu şu o için gibi kadar
    daha en çok az her hiç ise olan olarak olur oldu değil var yok üzere ancak
    """.split()
)


def normalize_tr(text: str) -> str:
    """Türkçe güvenli sadeleştirme: küçült, noktalamayı at, boşlukları tekle.

    Kısa cevap eşleştirmesi (T031) ve çeldirici→kaynak eşlemesi aynı normalizasyonu
    kullanır; iki yerde iki farklı kural olması sessiz tutarsızlık üretirdi.
    """
    lowered = text.translate(_TR_LOWER).lower()
    return " ".join(_WORD_RE.findall(lowered))


def _tokens(text: str) -> set[str]:
    return {word for word in normalize_tr(text).split() if len(word) > 2} - _STOPWORDS


def match_chunk(text: str, chunks: Sequence[RetrievedChunk]) -> UUID:
    """Bir metnin en çok örtüştüğü chunk'ı seçer.

    Çeldirici→kaynak eşlemesinin deterministik yanı burasıdır: skor yalnız kelime
    örtüşmesine bakar, modele sorulmaz. Hiçbir örtüşme yoksa listenin ilk (en
    yüksek skorlu) chunk'ına düşülür — sonuç her zaman retrieve edilmiş kümededir,
    yani "neden yanlış?" hiçbir durumda uydurma bir kaynağa işaret edemez.
    """
    needle = _tokens(text)
    best = chunks[0]
    best_score = -1.0
    for chunk in chunks:
        overlap = needle & _tokens(chunk.text)
        # Uzun chunk'lar tesadüfen daha çok örtüşür; kök karekökle bastırılır.
        score = len(overlap) / (len(_tokens(chunk.text)) ** 0.5 + 1)
        if score > best_score:
            best, best_score = chunk, score
    return best.chunk_id


# ---------------------------------------------------------------------------
# Modelden beklenen taslak şemalar
# ---------------------------------------------------------------------------
#
# Bunlar `schemas.assessment`'taki payload modellerinin AYNISI DEĞİLDİR ve olmamalı:
# taslakta `source_chunk_id` vardır (payload'da yoktur, sütuna gider) ve
# `distractor_sources` yoktur (modelden istenmez, biz üretiriz).


class _Draft(BaseModel):
    source_chunk_id: UUID


class _McqDraft(_Draft):
    stem: str = Field(min_length=5, max_length=4000)
    options: list[McqOption] = Field(min_length=2, max_length=6)
    answer_key: str
    explanation: str | None = Field(default=None, max_length=4000)


class _OpenDraft(_Draft):
    prompt: str = Field(min_length=5, max_length=4000)
    answer_key: str = Field(min_length=1, max_length=8000)
    key_points: list[str] = Field(default_factory=list, max_length=12)
    rubric: list[RubricItem] = Field(default_factory=list, max_length=12)
    accepted_answers: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _rubrik_agirliklari_yuze_tamamlanmali(self) -> _OpenDraft:
        """Ağırlık toplamı kısıtı YALNIZ ÜRETİMDE zorlanır (FR-117).

        Okuma yolunda normalize ediliyor (`schemas.assessment.normalized_rubric`),
        çünkü havuzda bugün toplamı 100 etmeyen onaylı sorular var ve kısıtı okuma
        yoluna koymak onları şema doğrulamasından düşürür, yani sessizce
        DEĞERLENDİRİLEMEZ hâle getirirdi. Yeni üretilen bir taslak için ise böyle
        bir bedel yok: kısıtı sağlamayan taslak havuza hiç girmez (fail-closed).
        """
        if self.rubric:
            toplam = sum(item.weight for item in self.rubric)
            if toplam != 100:
                raise ValueError(f"rubrik ağırlıkları 100 etmeli, {toplam} geldi")
        return self


class _CodeTraceDraft(_Draft):
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=8000)
    prompt: str = Field(min_length=5, max_length=2000)
    answer_key: str = Field(min_length=1, max_length=4000)
    explanation: str | None = Field(default=None, max_length=4000)


class _BugHuntDraft(_Draft):
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=8000)
    prompt: str = Field(min_length=5, max_length=2000)
    answer_key: BugHuntAnswerKey
    explanation: str | None = Field(default=None, max_length=4000)


_DRAFT_MODELS: dict[QuestionType, type[_Draft]] = {
    QuestionType.MCQ: _McqDraft,
    QuestionType.OPEN: _OpenDraft,
    QuestionType.CODE_TRACE: _CodeTraceDraft,
    QuestionType.BUG_HUNT: _BugHuntDraft,
}


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GenerationReport:
    """Üretim turunun sayımı. `accepted/returned` SC-009'un (≥ %98) ham verisidir."""

    requested: int
    returned: int = 0
    accepted: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)

    @property
    def rejected(self) -> int:
        return self.returned - self.accepted


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_TYPE_INSTRUCTIONS: dict[QuestionType, str] = {
    QuestionType.MCQ: (
        "Her soru için: stem (soru kökü), options (4 şık; her biri {key, text}, "
        "key 'A','B','C','D'), answer_key (doğru şıkkın key'i), explanation "
        "(doğru cevabın kaynağa dayalı kısa gerekçesi)."
    ),
    QuestionType.OPEN: (
        "Her soru için: prompt (soru metni), answer_key (beklenen cevap), "
        "key_points (cevapta bulunması gereken 2-5 madde), rubric "
        "(her biri {point, weight}; ağırlıklar toplamı 100)."
    ),
    QuestionType.CODE_TRACE: (
        "Her soru için: language (kodun dili), code (izlenecek kod parçası), "
        "prompt ('Bu kodun çıktısı nedir?' gibi), answer_key (beklenen çıktı, "
        "birebir), explanation (adım adım kısa gerekçe). Kod materyaldeki "
        "örneklerden türetilir; yeni kütüphane uydurma."
    ),
    QuestionType.BUG_HUNT: (
        "Her soru için: language, code (içinde TEK bir hata olan kod), prompt, "
        "answer_key ({line: hatalı satır numarası, bug_type: hatanın türü, "
        "fix_summary: düzeltmenin bir cümlelik özeti}), explanation."
    ),
}

_SHORT_ANSWER_INSTRUCTION = (
    "Bu sorular KISA CEVAP biçimindedir: cevap en fazla birkaç kelime olmalı. "
    "key_points ve rubric yerine accepted_answers alanını doldur: kabul edilecek "
    "karşılıkların listesi (eş anlamlılar, kısaltmalar, yaygın yazımlar). "
    "answer_key bunlardan en kanonik olanı olsun."
)

_SYSTEM_PROMPT = (
    "Sen bir üniversite dersinin sınav sorusu hazırlayan asistanısın. "
    "Yalnızca sana verilen ders materyalinden soru üretirsin; materyalde geçmeyen "
    "hiçbir bilgiyi kullanmazsın. Cevabın SADECE JSON olmalı: hiçbir açıklama, "
    "markdown kod çiti veya ek metin yazma. Tüm soru metinleri Türkçedir."
)


def _format_chunks(chunks: Sequence[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"### KAYNAK {index}\n"
        f"chunk_id: {chunk.chunk_id}\n"
        f"dosya: {chunk.file_name} · {chunk.location}\n"
        f"{chunk.text}"
        for index, chunk in enumerate(chunks, start=1)
    )


#: Zorluk seviyesinin prompt karşılığı. Tek sözlük: seviye adlarının ürün anlamı
#: burada yaşar, her çağrı yerinde yeniden hatırlanmaz (Anayasa XI).
_DIFFICULTY_INSTRUCTIONS: dict[QuestionDifficulty, str] = {
    QuestionDifficulty.EASY: "kolay — tanım ya da doğrudan hatırlama düzeyinde",
    QuestionDifficulty.MEDIUM: "orta — kavramı yeni bir örneğe uygulamayı gerektirsin",
    QuestionDifficulty.HARD: "zor — birden çok kavramı birlikte kullanmayı gerektirsin",
}


def build_prompt(
    *,
    topic_name: str,
    question_type: QuestionType,
    count: int,
    chunks: Sequence[RetrievedChunk],
    answer_format: AnswerFormat | None = None,
    example_questions: Sequence[str] = (),
    retry_hint: str | None = None,
    learning_outcome_text: str | None = None,
    difficulty: QuestionDifficulty | None = None,
) -> str:
    """Kullanıcı mesajını kurar. Şema tarifi ve kaynak listesi tek yerden gelir."""
    parts = [
        f'Konu: "{topic_name}". Aşağıdaki kaynaklardan {count} adet soru üret.',
        "",
        _TYPE_INSTRUCTIONS[question_type],
    ]
    # FR-113: çıktı ve zorluk prompt'a BİRER SATIR olarak girer. Ayrı bir talimat
    # bloğu yazılmadı — kalitesi ölçülmemiş bir yönlendirmeyi büyütmek, ölçmeden
    # iddia etmek olurdu (Anayasa III). Pedagojik kalitenin ölçümü T047'nin işi.
    if learning_outcome_text:
        parts.append(f"Bu soru şu öğrenme çıktısını ölçmeli: {learning_outcome_text}")
    if difficulty is not None:
        parts.append(f"Zorluk seviyesi: {_DIFFICULTY_INSTRUCTIONS[difficulty]}")
    if question_type is QuestionType.OPEN and answer_format is AnswerFormat.SHORT_ANSWER:
        parts.append(_SHORT_ANSWER_INSTRUCTION)
    parts += [
        "",
        "Her soruya ayrıca source_chunk_id ekle: sorunun dayandığı KAYNAK bloğunun "
        "chunk_id değeri, birebir kopyalanmış. Aşağıda listelenmeyen bir chunk_id "
        "yazarsan soru reddedilir.",
        "",
        'Çıktı biçimi: {"questions": [ ... ]} — dizideki her öğe bir sorudur.',
    ]
    if example_questions:
        parts += [
            "",
            "Eğitmenin örnek soruları — üslubu ve zorluk düzeyini bunlara benzet, "
            "ama sorularını birebir tekrarlama:",
            *(f"- {example}" for example in example_questions),
        ]
    if retry_hint:
        parts += ["", f"ÖNCEKİ DENEME REDDEDİLDİ: {retry_hint} Bu kez şemaya birebir uy."]
    parts += ["", "--- DERS MATERYALİ ---", "", _format_chunks(chunks)]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Ayrıştırma ve doğrulama
# ---------------------------------------------------------------------------


def extract_json_object(raw: str) -> dict[str, Any]:
    """Modelin metnindeki JSON nesnesini çıkarır.

    Sağlayıcılar zaman zaman JSON'u ```json çitiyle sarar. Çitleri temizlemek
    "şemaya uymayan çıktıyı kabul etmek" değildir: içerik yine tam doğrulamadan
    geçer, yalnız taşıyıcı gürültü atılır.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Beklenen JSON nesnesi değil.")
    return parsed


@dataclass(slots=True)
class _AttemptResult:
    """Tek bir model çağrısının sonucu.

    Soru düzeyindeki redler (`item_reasons`) ile yanıt düzeyindeki hatalar
    (`envelope_reason`) AYRI tutulur ve bu ayrım kozmetik değildir: SC-009
    "şema geçerliliği" oranının paydası **modelin döndürdüğü soru sayısıdır.**
    Ayrıştırılamayan bir yanıtı "iki soru geldi, ikisi de düştü" diye saymak
    oranı uydurulmuş bir paydayla raporlamak olurdu (Anayasa III).
    """

    drafts: list[_Draft] = field(default_factory=list)
    item_reasons: list[str] = field(default_factory=list)
    envelope_reason: str | None = None

    @property
    def returned(self) -> int:
        return len(self.drafts) + len(self.item_reasons)


def _drafts_from_response(raw: str, question_type: QuestionType) -> _AttemptResult:
    """Ham yanıttan geçerli taslakları çıkarır; her reddin sebebini de döndürür."""
    model = _DRAFT_MODELS[question_type]
    try:
        envelope = extract_json_object(raw)
    except (json.JSONDecodeError, ValueError):
        return _AttemptResult(envelope_reason="yanıt JSON olarak ayrıştırılamadı")

    items = envelope.get("questions")
    if not isinstance(items, list):
        return _AttemptResult(envelope_reason="yanıtta 'questions' dizisi yok")

    result = _AttemptResult()
    for item in items:
        if not isinstance(item, dict):
            result.item_reasons.append("şema: soru bir nesne değil")
            continue
        try:
            result.drafts.append(model.model_validate(item))
        except ValidationError as exc:
            result.item_reasons.append(f"şema: {exc.error_count()} alan hatalı")
    return result


def _payload_from_draft(
    draft: _Draft,
    *,
    question_type: QuestionType,
    chunks: Sequence[RetrievedChunk],
    answer_format: AnswerFormat | None,
) -> dict[str, Any]:
    """Taslağı saklanacak payload'a çevirir; deterministik alanları BURADA doldurur."""
    data = draft.model_dump(mode="json", exclude={"source_chunk_id"})

    if question_type is QuestionType.MCQ:
        assert isinstance(draft, _McqDraft)
        # Çeldirici→kaynak eşlemesi modelden değil, örtüşme skorundan.
        data["distractor_sources"] = {
            option.key: str(match_chunk(option.text, chunks))
            for option in draft.options
            if option.key != draft.answer_key
        }
    elif question_type is QuestionType.OPEN:
        data["format"] = (answer_format or AnswerFormat.ESSAY).value

    return data


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------


async def generate_questions(
    session: AsyncSession,
    *,
    course_id: UUID,
    topic: Topic,
    question_type: QuestionType,
    count: int,
    created_by: UUID,
    retriever: Retriever,
    completion: StructuredCompletion,
    answer_format: AnswerFormat | None = None,
    example_questions: Sequence[str] = (),
    retrieval_limit: int = 8,
    learning_outcome: LearningOutcome | None = None,
    difficulty: QuestionDifficulty | None = None,
) -> GenerationReport:
    """Konu adıyla retrieve edilen chunk'lardan `status=draft` soru üretir.

    Hiçbir koşulda istisna fırlatmaz (retrieval boşsa bile): rapor döner, kaç
    sorunun neden düştüğü sayılabilir olsun diye. Çağıran uç raporu olduğu gibi
    gösterir; "5 istendi, 5 üretildi" yazan bir arayüz, 3'ü düşmüşse yalan söyler.

    `topic` (kimlik değil, nesne) alınır çünkü retrieval sorgusu konunun ADIDIR;
    çağıran zaten konuyu yükleyip dersle eşleştirmiş olur.
    """
    report = GenerationReport(requested=count)

    chunks = await retriever.search(course_id=course_id, query=topic.name, limit=retrieval_limit)
    if not chunks:
        report.rejection_reasons.append("konuyla eşleşen ders materyali bulunamadı")
        logger.info(
            "soru üretimi kaynaksız durdu",
            extra={"context": {"course_id": str(course_id), "topic": topic.name}},
        )
        return report

    valid_ids = {chunk.chunk_id for chunk in chunks}

    attempt, attempt_reasons = await _request_drafts(
        completion,
        topic_name=topic.name,
        question_type=question_type,
        count=count,
        chunks=chunks,
        answer_format=answer_format,
        example_questions=example_questions,
        learning_outcome_text=(
            f"{learning_outcome.code}: {learning_outcome.description}"
            if learning_outcome is not None
            else None
        ),
        difficulty=difficulty,
    )
    # Payda yalnız modelin gerçekten döndürdüğü sorulardır; ayrıştırılamayan bir
    # yanıt sayıya değil, sebep listesine yazılır.
    report.returned = attempt.returned
    report.rejection_reasons.extend(attempt_reasons)
    report.rejection_reasons.extend(attempt.item_reasons)

    for draft in attempt.drafts:
        # 1. Kaynak uydurma kontrolü — düzeltme yok, atma var (Anayasa I).
        if draft.source_chunk_id not in valid_ids:
            report.rejection_reasons.append("kaynak uydurma: source_chunk_id retrieve edilmedi")
            continue

        payload = _payload_from_draft(
            draft,
            question_type=question_type,
            chunks=chunks,
            answer_format=answer_format,
        )

        # 2. Saklanacak payload, okunacağı şemayla doğrulanır. Taslak geçip payload
        #    geçmiyorsa hata bizdedir; yine de soruyu yazmayız (fail-closed).
        try:
            parse_payload(question_type, payload)
        except ValidationError as exc:
            report.rejection_reasons.append(f"payload şeması: {exc.error_count()} alan hatalı")
            continue

        question = Question(
            course_id=course_id,
            topic_id=topic.id,
            type=question_type,
            payload=payload,
            source_chunk_id=draft.source_chunk_id,
            status=QuestionStatus.DRAFT,
            created_by=created_by,
            # FR-113: üretilen taslak, istendiyse hücre ekseniyle birlikte doğar.
            # Verilmezse NULL kalır ve yayın kapısı onu "sınıflandırılmamış" diye
            # ayrıca raporlar — sessizce bir hücreye sayılmaz.
            learning_outcome_id=learning_outcome.id if learning_outcome is not None else None,
            difficulty=difficulty,
        )
        session.add(question)
        report.questions.append(question)
        report.accepted += 1

    await session.flush()

    logger.info(
        "soru üretimi tamamlandı",
        extra={
            "context": {
                "course_id": str(course_id),
                "topic_id": str(topic.id),
                "type": question_type.value,
                "requested": report.requested,
                "returned": report.returned,
                "accepted": report.accepted,
                "rejected": report.rejected,
            }
        },
    )
    return report


async def _request_drafts(
    completion: StructuredCompletion,
    *,
    topic_name: str,
    question_type: QuestionType,
    count: int,
    chunks: Sequence[RetrievedChunk],
    answer_format: AnswerFormat | None,
    example_questions: Sequence[str],
    learning_outcome_text: str | None = None,
    difficulty: QuestionDifficulty | None = None,
) -> tuple[_AttemptResult, list[str]]:
    """Modeli çağırır; hiç geçerli taslak çıkmazsa BİR KEZ yeniden dener (FR-020).

    İki değer döner: kullanılacak deneme sonucu ve **yanıt düzeyindeki** hata
    sebepleri. Yeniden deneme yalnız "hiçbiri geçmedi" durumunda yapılır; kısmen
    geçen bir turu tekrarlamak, geçenleri iki kez yazma riski getirirdi.
    """
    envelope_reasons: list[str] = []
    last = _AttemptResult()
    for attempt in range(2):
        prompt = build_prompt(
            topic_name=topic_name,
            question_type=question_type,
            count=count,
            chunks=chunks,
            answer_format=answer_format,
            example_questions=example_questions,
            retry_hint=("Çıktı şemaya uymadı." if attempt else None),
            learning_outcome_text=learning_outcome_text,
            difficulty=difficulty,
        )
        try:
            raw = await completion.complete(system=_SYSTEM_PROMPT, user=prompt)
        except Exception:  # sağlayıcı hatası üretimi düşürür, isteği patlatmaz
            logger.exception("soru üretiminde sağlayıcı hatası")
            envelope_reasons.append("sağlayıcı yanıt vermedi")
            continue

        last = _drafts_from_response(raw, question_type)
        if last.envelope_reason is not None:
            envelope_reasons.append(last.envelope_reason)
        if last.drafts:
            return last, envelope_reasons

    return last, envelope_reasons
