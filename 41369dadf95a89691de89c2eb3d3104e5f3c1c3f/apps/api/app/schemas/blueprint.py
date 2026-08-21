"""Blueprint ailesinin istek/yanıt sözleşmeleri (002 US3, T504).

Kendi modülünde yaşar: `schemas/assessment.py` bugün soru payload'ının dört tipini
ve sınav oturumu zarfını taşıyor, blueprint ise ayrı bir eksen. Aynı dosyaya
yığmak, iki şeridin aynı dosyaya dokunmasını da gerektirirdi.

**Alan adları İngilizce, kullanıcıya dönen metinler Türkçe.** Depoda kurulu ayrım
bu: `AnswerFeedbackOut.missing_points` İngilizce, içine yazılan `answers.feedback`
jsonb anahtarları (`eksik_noktalar`) Türkçe ve hata cümleleri Türkçe (Anayasa V).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.assessment import ExamVersionStatus, QuestionDifficulty, QuestionType

# ---------------------------------------------------------------------------
# Öğrenme çıktıları (FR-110)
# ---------------------------------------------------------------------------


class LearningOutcomeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=1000)
    topic_id: UUID | None = None


class LearningOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: str
    topic_id: UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Dağılım hücreleri (FR-111, FR-112)
# ---------------------------------------------------------------------------


class BlueprintCellIn(BaseModel):
    learning_outcome_id: UUID
    difficulty: QuestionDifficulty
    question_type: QuestionType
    question_count: int = Field(ge=1, le=100)
    points_per_question: int = Field(default=1, ge=1, le=100)


class BlueprintCellOut(BlueprintCellIn):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    #: Türkçe hücre adı — hata ve rapor metinleri bunu kullanır, istemci kendi
    #: etiketini uydurmaz (Anayasa V).
    label: str


class DistributionTargets(BaseModel):
    """Arayüzün aldığı MARJİNAL dağılım; hücrelerin ona uyup uymadığı sınanır.

    Yüzdeler saklanmaz: ekran "%40 kolay" alır, tam sayıya çevirir ve buraya ADET
    gönderir. Yuvarlamayı istemci yapar, ama yuvarlamanın tuttuğunu sunucu
    doğrular — SC-003'ün "birebir uyar" iddiası ancak böyle karar verilebilir olur.

    Hepsi opsiyonel: yalnız hücre göndermek de geçerli bir kullanımdır.
    """

    total_questions: int | None = Field(default=None, ge=1, le=1000)
    by_difficulty: dict[QuestionDifficulty, int] | None = None
    by_question_type: dict[QuestionType, int] | None = None


# ---------------------------------------------------------------------------
# Blueprint (FR-111)
# ---------------------------------------------------------------------------


class BlueprintCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    duration_minutes: int = Field(ge=1, le=600)
    max_attempts: int = Field(default=1, ge=1, le=100)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    cells: list[BlueprintCellIn] = Field(min_length=1, max_length=200)
    targets: DistributionTargets | None = None


class BlueprintUpdate(BaseModel):
    """Hücreler verilirse KÜME OLARAK değişir (sil + yaz).

    Tek hücrelik güncelleme bilerek yok: FR-112 doğrulaması küme üzerinde yapılır
    ve tekil bir UPDATE doğrulamayı atlayıp tutarsız bir dağılım bırakabilirdi.
    Veritabanı da aynı kararı taşıyor — `blueprint_cells`'te UPDATE ne politikası
    ne yetkisi var.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    max_attempts: int | None = Field(default=None, ge=1, le=100)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    cells: list[BlueprintCellIn] | None = Field(default=None, min_length=1, max_length=200)
    targets: DistributionTargets | None = None


class TopicShare(BaseModel):
    """Konu dağılımı — TÜRETİLMİŞ ve salt okunur (data-model.md §8 madde 2).

    `topic_id` NULL olan çıktılar `topic_id=None` satırında toplanır ve ekranda
    "konusuz çıktıdan geliyor" diye gösterilir; sessizce yuvarlanmaz (Anayasa III).
    """

    topic_id: UUID | None
    topic_name: str | None
    question_count: int


class BlueprintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    title: str
    description: str | None
    duration_minutes: int
    max_attempts: int
    opens_at: datetime | None
    closes_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cells: list[BlueprintCellOut]
    #: SUM(cells.question_count) — kolon değil, türetilmiş. Tutarsız olamaz.
    total_questions: int
    total_points: int
    topic_distribution: list[TopicShare]
    published_version_no: int | None = None


# ---------------------------------------------------------------------------
# Sürümler (FR-114, FR-115)
# ---------------------------------------------------------------------------


class ExamVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    blueprint_id: UUID
    version_no: int
    status: ExamVersionStatus
    published_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime
    item_count: int = 0
    total_points: int = 0


class ExamItemIn(BaseModel):
    question_id: UUID
    #: Verilmezse gönderim sırası kullanılır.
    position: int | None = Field(default=None, ge=1, le=1000)


class ExamItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    question_id: UUID
    points: int
    question_type: QuestionType
    difficulty: QuestionDifficulty | None
    learning_outcome_id: UUID | None
    stem: str


class MissingCell(BaseModel):
    """İstenen adet ile dolan adet tutmayan hücre (FR-114)."""

    learning_outcome_id: UUID
    difficulty: QuestionDifficulty
    question_type: QuestionType
    required: int
    filled: int
    label: str


class UnclassifiedItem(BaseModel):
    """Kalemde olup hiçbir hücreye sayılamayan soru (data-model.md §8 madde 7).

    Eksik hücreden AYRI raporlanır: tek listede görünseydi başka bir hücre
    eksikmiş gibi okunur, öğretmen o hücreye soru eklemeye çalışır ve gerçek sebep
    hiç söylenmemiş olurdu.
    """

    question_id: UUID
    position: int
    missing_fields: list[str]
    label: str


class ReadinessOut(BaseModel):
    """Yayın kapısının raporu. `ready` ancak İKİ liste de boşsa true olur."""

    ready: bool
    missing_cells: list[MissingCell]
    unclassified_items: list[UnclassifiedItem]
    message: str


class PublishOut(BaseModel):
    version: ExamVersionOut
    #: Yayın anında dondurulan dağılım kanıtı (data-model.md §8 madde 1).
    blueprint_snapshot: list[dict[str, Any]]
    message: str
