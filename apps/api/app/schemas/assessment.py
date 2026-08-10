"""Ölçme (assessment) API sözleşmeleri.

Üç ayrı katman burada:

1. **Konu şemaları** — `topics` ucunun girdi/çıktısı.
2. **`payload` biçimleri** — `questions.payload` jsonb'sinin tip bazlı şekli
   (03_ASSESSMENT_BRIEF §"payload jsonb biçimleri"). Bunlar hem soru üretiminin
   (T029) doğrulama yüzeyi hem puanlamanın (T031) okuma yüzeyidir; ikisi de aynı
   modeli kullanır, biçim iki yerde tarif edilmez (Anayasa XI).
3. **Uç şemaları** — soru havuzu ve sınav uçlarının gövdeleri.

`payload` doğrudan istemciye verilmez: `public_payload()` bir **beyaz listeden**
geçirir. Cevap anahtarı, çeldirici kaynakları ve rubrik öğrenciye gitmez; liste
beyaz olduğu için ileride payload'a eklenen bir alan yanlışlıkla sızamaz
(fail-closed, Anayasa IV).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.assessment import ExamMode, QuestionDifficulty, QuestionStatus, QuestionType

# ---------------------------------------------------------------------------
# Konular
# ---------------------------------------------------------------------------


class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200, examples=["Deadlock"])


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    name: str
    created_by: UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# payload biçimleri
# ---------------------------------------------------------------------------


class AnswerFormat(StrEnum):
    """`open` tipinin alt türü (FR-036, KARARLAR_SERIT4.md Karar 4).

    Beşinci bir `question_type` değeri DEĞİLDİR: hocanın istediği "klasik / kısa
    cevap" ayrımı değerlendirme mantığını değiştirir, soru tipini değil.
    `essay` rubrikle LLM'e değerlendirtilir; `short_answer` `accepted_answers`
    listesiyle deterministik eşleştirilir.
    """

    ESSAY = "essay"
    SHORT_ANSWER = "short_answer"


class McqOption(BaseModel):
    key: str = Field(min_length=1, max_length=2, examples=["A"])
    text: str = Field(min_length=1, max_length=1000)


class McqPayload(BaseModel):
    stem: str = Field(min_length=5, max_length=4000)
    options: list[McqOption] = Field(min_length=2, max_length=6)
    answer_key: str
    #: Her yanlış şıkkın çeliştiği chunk. "Neden yanlış?"ın deterministik yakıtı
    #: (FR-021): kaynak bölümü modelden değil buradan, chunk metadata'sından gelir.
    distractor_sources: dict[str, UUID]
    explanation: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _check_keys(self) -> McqPayload:
        keys = [option.key for option in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError("Şık anahtarları benzersiz olmalı.")
        if self.answer_key not in keys:
            raise ValueError("answer_key şıklardan biri olmalı.")
        distractors = set(keys) - {self.answer_key}
        if set(self.distractor_sources) != distractors:
            # Eksik bırakmak "neden yanlış?"ı bazı şıklarda sessizce çalışmaz hâle
            # getirirdi; boş bırakmaktansa soruyu şemadan geçirmemek yeğdir.
            raise ValueError("distractor_sources tüm yanlış şıkları kapsamalı.")
        return self


class RubricItem(BaseModel):
    point: str = Field(min_length=1, max_length=500)
    weight: int = Field(ge=1, le=100)


class RubricCriterionScore(BaseModel):
    """Bir ölçütten alınan puan (FR-117).

    `weight` normalize edilmiş ağırlıktır; `earned` = weight × score / 100. Toplam
    puan bu satırlardan TÜRETİLİR, modelden okunmaz — model hem kırılım hem ayrı bir
    toplam verseydi ikisi çelişebilirdi ve öğrenciye gösterilen tablonun toplamı
    tutmazdı (Anayasa III).
    """

    point: str
    weight: int
    score: int = Field(ge=0, le=100)
    earned: int


def normalized_rubric(rubric: list[RubricItem]) -> list[RubricItem]:
    """Ağırlıkları 100'e tamamlar.

    **Okuma yolunda normalize edilir, kısıt olarak dayatılmaz.** Havuzda bugün
    ağırlıkları 100 etmeyen onaylı sorular var (`OpenPayload.rubric` toplamı hiç
    doğrulamadı) ve toplamı şema kısıtına çevirmek onları şema doğrulamasından
    düşürür, yani sessizce DEĞERLENDİRİLEMEZ hâle getirirdi. Kısıt yalnız yeni
    üretimde zorlanır (`question_gen`).

    Yuvarlama artığı en büyük ağırlıklı ölçüte eklenir; toplam her zaman tam 100
    olur, yoksa öğrenciye gösterilen tablonun toplamı tutmaz.
    """
    if not rubric:
        return []
    total = sum(item.weight for item in rubric)
    if total == 100:
        return list(rubric)

    scaled = [
        RubricItem(point=item.point, weight=max(1, round(item.weight * 100 / total)))
        for item in rubric
    ]
    fark = 100 - sum(item.weight for item in scaled)
    if fark:
        en_buyuk = max(range(len(scaled)), key=lambda i: scaled[i].weight)
        scaled[en_buyuk] = RubricItem(
            point=scaled[en_buyuk].point, weight=max(1, scaled[en_buyuk].weight + fark)
        )
    return scaled


class OpenPayload(BaseModel):
    prompt: str = Field(min_length=5, max_length=4000)
    answer_key: str = Field(min_length=1, max_length=8000)
    #: `eksik_noktalar` bunlara karşı çıkarılır.
    key_points: list[str] = Field(default_factory=list, max_length=12)
    rubric: list[RubricItem] = Field(default_factory=list, max_length=12)
    format: AnswerFormat = AnswerFormat.ESSAY
    #: Yalnız `short_answer`: kabul edilen karşılıklar (eş anlamlı/kısaltma dahil).
    accepted_answers: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _check_format(self) -> OpenPayload:
        if self.format is AnswerFormat.SHORT_ANSWER:
            if not self.accepted_answers:
                raise ValueError("short_answer için accepted_answers boş olamaz.")
        elif not self.key_points:
            raise ValueError("essay için key_points boş olamaz.")
        return self


class CodeTracePayload(BaseModel):
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=8000)
    prompt: str = Field(min_length=5, max_length=2000)
    answer_key: str = Field(min_length=1, max_length=4000)
    explanation: str | None = Field(default=None, max_length=4000)


class BugHuntAnswerKey(BaseModel):
    line: int = Field(ge=1)
    bug_type: str = Field(min_length=1, max_length=200)
    fix_summary: str = Field(min_length=1, max_length=2000)


class BugHuntPayload(BaseModel):
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=8000)
    prompt: str = Field(min_length=5, max_length=2000)
    answer_key: BugHuntAnswerKey
    explanation: str | None = Field(default=None, max_length=4000)


PAYLOAD_MODELS: dict[QuestionType, type[BaseModel]] = {
    QuestionType.MCQ: McqPayload,
    QuestionType.OPEN: OpenPayload,
    QuestionType.CODE_TRACE: CodeTracePayload,
    QuestionType.BUG_HUNT: BugHuntPayload,
}

#: Öğrenciye gösterilebilir payload alanları. Beyaz liste: burada olmayan her alan
#: düşer. Yeni bir alan (ör. `answer_key_regex`) eklendiğinde varsayılan davranış
#: "sızdırma" değil "gizle" olsun diye böyle.
_PUBLIC_PAYLOAD_KEYS: dict[QuestionType, tuple[str, ...]] = {
    QuestionType.MCQ: ("stem", "options"),
    QuestionType.OPEN: ("prompt", "format"),
    QuestionType.CODE_TRACE: ("language", "code", "prompt"),
    QuestionType.BUG_HUNT: ("language", "code", "prompt"),
}

#: Sınav bittikten sonra öğrenciye açılan alanlar: artık öğrenme materyalidir.
_SOLUTION_KEYS: tuple[str, ...] = ("answer_key", "explanation", "key_points", "rubric")


def parse_payload(question_type: QuestionType, raw: dict[str, Any]) -> BaseModel:
    """Ham jsonb'yi tipine karşılık gelen modele çevirir.

    Şemaya uymayan payload burada `pydantic.ValidationError` fırlatır; çağıran
    bunu ya soruyu havuza yazmayarak (T029) ya da değerlendirmeyi tamamlamayarak
    (T031) karşılar — ikisi de fail-closed.
    """
    model = PAYLOAD_MODELS[question_type]
    return model.model_validate(raw)


def public_payload(question_type: QuestionType, raw: dict[str, Any]) -> dict[str, Any]:
    """Öğrenciye gösterilebilir payload. Bilinmeyen tipte boş döner (fail-closed)."""
    allowed = _PUBLIC_PAYLOAD_KEYS.get(question_type, ())
    return {key: raw[key] for key in allowed if key in raw}


def solution_payload(question_type: QuestionType, raw: dict[str, Any]) -> dict[str, Any]:
    """Sınav bittikten sonra açılan çözüm alanları (cevap anahtarı + açıklama)."""
    _ = question_type  # tip bazlı ayrım bugün yok; imza ileride daralmaya açık.
    return {key: raw[key] for key in _SOLUTION_KEYS if key in raw}


# ---------------------------------------------------------------------------
# Ortak çıktı parçaları
# ---------------------------------------------------------------------------


class SourceRefOut(BaseModel):
    """Kaynak referansı. Dosya adı ve konum **chunk metadata'sından** gelir.

    Model metninden üretilmez (Anayasa I); bu yüzden burada bir `text` alanı değil,
    kısaltılmış `snippet` vardır — gösterilen alıntı gerçekten o chunk'ın içindedir.
    """

    chunk_id: UUID
    file_name: str
    location: str
    snippet: str


# ---------------------------------------------------------------------------
# Soru havuzu uçları
# ---------------------------------------------------------------------------


class QuestionOut(BaseModel):
    id: UUID
    course_id: UUID
    topic_id: UUID
    type: QuestionType
    #: Eğitmene tam payload, öğrenciye `public_payload()` süzgecinden geçmiş hâli.
    payload: dict[str, Any]
    status: QuestionStatus
    created_by: UUID | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    #: Eğitmen soruyu kaynağını görerek onaylar (FR-023). Öğrenciye de gösterilir:
    #: onaylı sorunun hangi materyalden geldiği gizli değildir.
    source: SourceRefOut | None = None
    #: Sorunun dayandığı belgenin yerine açıkça yeni bir sürüm yüklendiyse true.
    #: Bayatlık ayrı bir bayrak olarak saklanmaz; belge sürüm zincirinden türetilir.
    source_stale: bool = False
    #: Hücre ekseni (0008). NULL ise soru hiçbir blueprint hücresine sayılmaz ve
    #: yayın kapısı onu "sınıflandırılmamış" diye ayrıca raporlar. Havuz ekranının
    #: bunu göstermesi gerekir, yoksa öğretmen kapıya çarpana kadar fark etmez.
    learning_outcome_id: UUID | None = None
    difficulty: QuestionDifficulty | None = None


class QuestionGenerateRequest(BaseModel):
    """Eğitmenin kurduğu çerçeve (6 Ağustos toplantısı: biçimi eğitmen seçer).

    `example_questions` verilirse üretim o üslubu taklit eder; verilmezse yalnız
    materyalden gidilir.
    """

    topic_id: UUID
    question_type: QuestionType = QuestionType.MCQ
    #: Yalnız `open` için anlamlı: klasik mi kısa cevap mı (Karar 4).
    answer_format: AnswerFormat | None = None
    count: int | None = Field(default=None, ge=1, le=20)
    example_questions: list[str] = Field(default_factory=list, max_length=5)


class QuestionGenerationOut(BaseModel):
    """Üretim raporu. `accepted/returned` oranı SC-009'un ölçüm girdisidir."""

    requested: int
    returned: int
    accepted: int
    rejected: int
    #: Neden düştüğü sayılabilsin diye: "şema", "kaynak uydurma", "konu dışı chunk".
    rejection_reasons: list[str] = Field(default_factory=list)
    questions: list[QuestionOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sınav uçları
# ---------------------------------------------------------------------------


class ExamStartRequest(BaseModel):
    mode: ExamMode = ExamMode.PRACTICE
    #: Verilirse yalnız o konunun onaylı soruları çekilir.
    topic_id: UUID | None = None
    #: Verilirse blueprint sınavı açılır: kâğıt yayınlanmış sürümün `exam_items`'ından
    #: gelir, `topic_id` ve rastgele seçim devre dışı kalır (0008, FR-115/FR-116).
    blueprint_id: UUID | None = None


class ExamQuestionOut(BaseModel):
    id: UUID
    type: QuestionType
    payload: dict[str, Any]
    answered: bool


class ExamSessionOut(BaseModel):
    id: UUID
    course_id: UUID
    mode: ExamMode
    started_at: datetime
    #: Kırpılmış etkin bitiş (Karar 2): `min(expires_at, started_at + süre)`.
    expires_at: datetime | None
    #: Sunucudan hesaplanır; istemci saatine güvenilmez. practice modda None.
    remaining_seconds: int | None
    expired: bool
    finished_at: datetime | None
    #: `answers` satırlarından yeniden hesaplanır, `exam_sessions.score`'dan okunmaz.
    score: float | None
    question_count: int
    answered_count: int
    questions: list[ExamQuestionOut] = Field(default_factory=list)
    #: Blueprint sınavında oturumun bağlandığı sürüm. Prova oturumlarında None.
    #: Yürüyen oturum bu sürümü görmeye devam eder; yeni sürüm yayınlanması
    #: başlamış bir sınavı değiştirmez (data-model.md §8 madde 9).
    exam_version_id: UUID | None = None
    exam_blueprint_id: UUID | None = None
    attempt_no: int | None = None


class AnswerSubmitRequest(BaseModel):
    question_id: UUID
    given: str = Field(min_length=1, max_length=8000)
    #: Öğrencinin bu soruda kullandığı ipucu kademesi. `exam` modunda 0 dışında
    #: her değer reddedilir; `practice` modunda mastery çarpanına girer.
    hint_level: int = Field(default=0, ge=0, le=4)


class AnswerFeedbackOut(BaseModel):
    question_id: UUID
    #: Cevap kaydedildi mi (her zaman True; kaydedilemezse hata döner).
    recorded: bool = True
    #: Değerlendirme tamamlandı mı. False ise puan gösterilmez (FR-020).
    graded: bool
    is_correct: bool | None = None
    score: int | None = None
    missing_points: list[str] = Field(default_factory=list)
    #: MCQ'da seçilen çeldiricinin çeliştiği kaynak bölümü (FR-021).
    why_wrong: SourceRefOut | None = None
    #: Açık uçluda değerlendirmenin dayandığı kaynak.
    evidence: SourceRefOut | None = None
    #: Sınav bitince açılan cevap anahtarı + açıklama; öncesinde None.
    solution: dict[str, Any] | None = None
    #: Rubriğe bağlı sorularda ölçüt kırılımı (FR-117). Yalnız çözüm açıldığında
    #: dolar: sınav sürerken hangi ölçütten kaç aldığını görmek, cevap anahtarını
    #: parça parça okumaktır.
    rubric_breakdown: list[RubricCriterionScore] = Field(default_factory=list)
    message: str | None = None


class ExamFinishOut(BaseModel):
    session_id: UUID
    #: Cevaplanan soruların ortalaması. Hiç cevap yoksa None — 0 değil.
    score: float | None
    answered_count: int
    #: Cevaplanmamış sorular: boş sayılır, yanlış değil, puana katılmaz.
    unanswered_count: int
    #: Kaydedilmiş ama değerlendirmesi tamamlanamamış cevaplar (FR-020).
    ungraded_count: int
    message: str
    results: list[AnswerFeedbackOut] = Field(default_factory=list)


class HintRequest(BaseModel):
    question_id: UUID
    hint_level: int = Field(default=1, ge=1, le=4)


class HintOut(BaseModel):
    question_id: UUID
    hint_level: int
    text: str
    source: SourceRefOut
