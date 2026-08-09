"""Sohbet tabloları: oturum, mesaj, cevap önbelleği, istek ölçüm kaydı.

Şemanın kaynağı `supabase/migrations/0003_chat.sql` dosyasıdır; buradaki modeller o
şemayı yansıtır. Migration'lar düz SQL olarak tutulur, ORM'den üretilmez.

Enum'lar için not: `mode`, `status` ve `socratic_stage` sütunları `app/contracts.py`
içindeki sözleşme enum'larına DOĞRUDAN bağlanır, yerel kopya tanımlanmaz. Sebep:
sözleşme ile şema arasında ikinci bir enum tanımı olsaydı, biri güncellenip diğeri
unutulduğunda hata çalışma zamanında ve sessizce ortaya çıkardı.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import TIMESTAMP, Boolean, Integer, SmallInteger, Text, func
from sqlalchemy import ForeignKey as FK
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.contracts import AnswerStatus, ChatMode, SocraticStage
from app.models.base import Base, created_at, pg_enum, uuid_fk, uuid_pk

# core.py ve assessment.py'deki yardımcının aynısı; ÜÇÜNCÜ bir kopya yazmak yerine
# içe aktarılıyor (Anayasa XI, tekrarsızlık). Kalıcı çözüm helper'ı `models/base.py`'ye
# taşımaktır — o dosya bu şeridin sahipliğinde değil, gruba iletildi.


class ChatRole(StrEnum):
    """Mesajın sahibi. `contracts.py`'de yok çünkü modüller arası bir tip değil."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    user_id: Mapped[uuid_fk] = mapped_column(FK("profiles.id", ondelete="CASCADE"))
    mode: Mapped[ChatMode] = mapped_column(pg_enum(ChatMode, "chat_mode"), default=ChatMode.QA)
    # Sokratik merdivenin kalıcı hâli; biçimi `modules/assessment/socratic.py` belirler.
    # Oturum yeniden yüklense de kademe korunur (FR-014).
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at]
    # base.py'deki `ts_now`a taşınmadı: `onupdate` sahibi tek kolon bu, üçüncü bir
    # takma ad tek kullanıcısı olan bir soyutlama olurdu.
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid_pk]
    session_id: Mapped[uuid_fk] = mapped_column(FK("chat_sessions.id", ondelete="CASCADE"))
    # Denormalize: izolasyon filtresi chat_sessions'a JOIN etmeden ifade edilir.
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    role: Mapped[ChatRole] = mapped_column(pg_enum(ChatRole, "chat_role"))
    content: Mapped[str] = mapped_column(Text)
    # Dosya adı ve konum chunk metadata'sından üretilmiş hâliyle saklanır (Anayasa I).
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Kullanıcı mesajlarında NULL (şemadaki CHECK bunu zorlar).
    status: Mapped[AnswerStatus | None] = mapped_column(pg_enum(AnswerStatus, "answer_status"))
    socratic_stage: Mapped[SocraticStage | None] = mapped_column(
        pg_enum(SocraticStage, "socratic_stage")
    )
    # Tur içi sıra (kullanıcı 0, asistan 1). Turlar arası sıra created_at'tedir;
    # tek başına yetmez çünkü now() işlem zaman damgasıdır. Bkz. 0003_chat.sql.
    seq: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[created_at]


class AnswerCache(Base):
    """Birebir eşleşmeli önbellek (FR-034). Benzerlik tabanlı eşleşme YOKTUR."""

    __tablename__ = "answer_cache"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    # sha256(mode + '\n' + normalize edilmiş soru) — bkz. app/api/chat.py:question_hash.
    question_hash: Mapped[str] = mapped_column(Text)
    # Guardrail zincirinden geçmiş cevap zarfı.
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[created_at]


class RequestLog(Base):
    """İstek ölçüm kaydı (FR-035, Anayasa III).

    Serbest metin taşımaz: soru ve cevap metni buraya YAZILMAZ. Kişisel veri
    redaksiyonu böylece bir filtreye değil şemaya dayanır.
    """

    __tablename__ = "request_logs"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    user_id: Mapped[uuid_fk] = mapped_column(FK("profiles.id", ondelete="CASCADE"))
    route: Mapped[str] = mapped_column(Text)
    mode: Mapped[ChatMode] = mapped_column(pg_enum(ChatMode, "chat_mode"))
    status: Mapped[AnswerStatus | None] = mapped_column(pg_enum(AnswerStatus, "answer_status"))
    http_status: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[created_at]


__all__ = [
    "AnswerCache",
    "ChatMessage",
    "ChatRole",
    "ChatSession",
    "RequestLog",
]
