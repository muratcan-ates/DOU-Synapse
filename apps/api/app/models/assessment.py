"""Ölçme (assessment) tabloları: konu, soru, sınav oturumu, cevap, mastery.

Şemanın kaynağı `supabase/migrations/0004_assessment.sql` dosyasıdır; buradaki modeller
o şemayı yansıtır. Migration'lar düz SQL olarak tutulur, ORM'den üretilmez.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy import ForeignKey as FK
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, pg_enum, uuid_fk, uuid_pk


class QuestionType(StrEnum):
    MCQ = "mcq"
    OPEN = "open"
    CODE_TRACE = "code_trace"
    BUG_HUNT = "bug_hunt"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExamMode(StrEnum):
    PRACTICE = "practice"
    EXAM = "exam"


class QuestionDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExamVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid_fk] = mapped_column(FK("profiles.id"))
    created_at: Mapped[created_at]


class LearningOutcome(Base):
    """Dersin ölçülebilir kazanımı — soru, hücre ve raporlama bu eksene bağlanır.

    `topics`'ten ayrı bir tablodur: konu bir ARAMA KOLU (soru üretiminin retrieval
    sorgusu `topic.name`'dir), çıktı bir ÖLÇÜLEBİLİR İDDİA. `topic_id` köprüsü
    üretimin bugünkü davranışını korumak için var ve konu dağılımı da bu köprüden
    türetilir (0008, data-model.md §2.2).
    """

    __tablename__ = "learning_outcomes"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    topic_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("topics.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid_fk] = mapped_column(FK("profiles.id"))
    created_at: Mapped[created_at]


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid_fk] = mapped_column(FK("topics.id", ondelete="CASCADE"))
    type: Mapped[QuestionType] = mapped_column(pg_enum(QuestionType, "question_type"))
    # Dört tipin ortak zarfı (biçim R3 brief §2'de sabit): mcq/open/code_trace/bug_hunt.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_chunk_id: Mapped[uuid_fk] = mapped_column(FK("chunks.id", ondelete="RESTRICT"))
    status: Mapped[QuestionStatus] = mapped_column(
        pg_enum(QuestionStatus, "question_status"), default=QuestionStatus.DRAFT
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("profiles.id", ondelete="SET NULL")
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("profiles.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[created_at]
    # Hücre ekseni (0008). İkisi de nullable ve VARSAYILANSIZ: havuzdaki bir sorunun
    # hangi kazanımı ölçtüğünü göç bilemez ve 'medium' gibi bir varsayılan, ölçülmemiş
    # bir iddiayı veriye yazmak olurdu (Anayasa III). Kuralı zorlayan tek yer yayın
    # kapısıdır ve orada "sınıflandırılmamış kalem" olarak ayrıca raporlanır.
    learning_outcome_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("learning_outcomes.id", ondelete="SET NULL")
    )
    difficulty: Mapped[QuestionDifficulty | None] = mapped_column(
        pg_enum(QuestionDifficulty, "question_difficulty")
    )


class ExamBlueprint(Base):
    """Sınavın çatısı — sorulardan ÖNCE var.

    Toplam soru sayısı KOLON DEĞİLDİR: `SUM(blueprint_cells.question_count)`'tur.
    Türetilmiş olduğu için tutarsız olamaz.
    """

    __tablename__ = "exam_blueprints"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=1)
    # NULL = o yönde sınır yok. Ters pencere kısıtla ifade edilemez kılınmıştır.
    opens_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_by: Mapped[uuid_fk] = mapped_column(FK("profiles.id"))
    created_at: Mapped[created_at]
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class BlueprintCell(Base):
    """Dağılımın atomik birimi: (çıktı × zorluk × tip) → kaç soru, kaçar puan.

    Yüzdeler SAKLANMAZ: arayüz marjinal dağılım alır, API tam sayı hücrelere açar.
    Hücre kümesi bütün olarak DELETE+INSERT ile değişir — UPDATE ne politikası ne
    yetkisi vardır, çünkü FR-112 doğrulaması küme üzerinde yapılır ve tek hücrelik
    bir güncelleme doğrulamayı atlayıp tutarsız bir dağılım bırakabilirdi.
    """

    __tablename__ = "blueprint_cells"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    blueprint_id: Mapped[uuid_fk] = mapped_column(FK("exam_blueprints.id", ondelete="CASCADE"))
    learning_outcome_id: Mapped[uuid_fk] = mapped_column(
        FK("learning_outcomes.id", ondelete="RESTRICT")
    )
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        pg_enum(QuestionDifficulty, "question_difficulty")
    )
    question_type: Mapped[QuestionType] = mapped_column(pg_enum(QuestionType, "question_type"))
    question_count: Mapped[int] = mapped_column(SmallInteger)
    points_per_question: Mapped[int] = mapped_column(SmallInteger, default=1)


class ExamVersion(Base):
    """Yayınlanmış bir sınavın dondurulmuş hâli; oturumlar buna bağlanır.

    Soru payload'ı SNAPSHOT'lanmaz (içerik zaten değişmez, kimlikle referans yeter),
    ama DAĞILIM donar: `blueprint_cells` düzenlenebilir olduğu için, yayından sonra
    hücreler değişirse "blueprint'e birebir uydu" iddiası yeniden üretilemez hâle
    gelirdi (data-model.md §8 madde 1).
    """

    __tablename__ = "exam_versions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    blueprint_id: Mapped[uuid_fk] = mapped_column(FK("exam_blueprints.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[ExamVersionStatus] = mapped_column(
        pg_enum(ExamVersionStatus, "exam_version_status"), default=ExamVersionStatus.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    published_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("profiles.id", ondelete="SET NULL")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # Yayın anında kapının doğruladığı hücre kümesi. Toplulaştırılmaz, bütün olarak
    # okunur ve bir daha yazılmaz.
    blueprint_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[created_at]


class ExamItem(Base):
    """Bir sürümdeki kâğıdın sırası ve puanı.

    `blueprint_cell_id` BİLEREK YOKTUR: kalemin hangi hücreyi doldurduğu
    `questions`'ın üç alanından türetilir. `points` ise yayın anında kopyalanır —
    blueprint sonradan düzenlense de yayınlanmış kâğıdın puanlaması değişmez.
    """

    __tablename__ = "exam_items"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    exam_version_id: Mapped[uuid_fk] = mapped_column(FK("exam_versions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    question_id: Mapped[uuid_fk] = mapped_column(FK("questions.id", ondelete="RESTRICT"))
    points: Mapped[int] = mapped_column(SmallInteger)


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    user_id: Mapped[uuid_fk] = mapped_column(FK("profiles.id", ondelete="CASCADE"))
    mode: Mapped[ExamMode] = mapped_column(pg_enum(ExamMode, "exam_mode"))
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # practice modda NULL (süresiz). exam modda kalan süre buradan hesaplanır, istemci
    # saatine güvenilmez.
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    score: Mapped[float | None] = mapped_column(Numeric)
    # Oturum açılırken seçilen sorular sabitlenir; sonradan onay/red bu listeyi değiştirmez.
    #
    # 0008'den beri NULL olabilir. İki akış yan yana yaşıyor ve kâğıdın kaynağı
    # tektir (`exam_sessions_paper_source` kısıtı bunu ifade edilemez kılar):
    #   exam_version_id IS NULL     → self-servis prova, kaynak burasıdır
    #   exam_version_id IS NOT NULL → blueprint sınavı, kaynak `exam_items`
    # Okuyan her yol `paper_question_ids()` üzerinden geçer; doğrudan okunmaz.
    question_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    # Blueprint bağı — hepsi INSERT anında yazılır, UPDATE yetkisi istenmez (0007'nin
    # süre koruması geri alınmasın diye).
    exam_version_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("exam_versions.id", ondelete="RESTRICT")
    )
    exam_blueprint_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("exam_blueprints.id", ondelete="RESTRICT")
    )
    attempt_no: Mapped[int | None] = mapped_column(SmallInteger)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid_pk]
    session_id: Mapped[uuid_fk] = mapped_column(FK("exam_sessions.id", ondelete="CASCADE"))
    question_id: Mapped[uuid_fk] = mapped_column(FK("questions.id", ondelete="RESTRICT"))
    # Denormalize: RLS filtresi exam_sessions'a JOIN etmeden tek satırda ifade edilir.
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    given: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None]
    score: Mapped[int | None] = mapped_column(Integer)
    hint_level: Mapped[int] = mapped_column(Integer, default=0)
    # {"score": 0-100, "eksik_noktalar": [...], "dayanak_chunk_id": "..."}
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    answered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class Mastery(Base):
    __tablename__ = "mastery"

    user_id: Mapped[uuid_fk] = mapped_column(
        FK("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid_fk] = mapped_column(FK("topics.id", ondelete="CASCADE"), primary_key=True)
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    score: Mapped[float]
    # "İlk cevap mı" sorusunu cevaplar (mastery/service.py'deki başlangıç davranışı, T036).
    answer_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
