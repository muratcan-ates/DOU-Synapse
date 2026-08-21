"""Çekirdek tablolar: profil, ders, üyelik, belge, chunk, ingestion işi.

Şemanın kaynağı `supabase/migrations/0001_core_schema.sql` dosyasıdır; buradaki modeller
o şemayı yansıtır. Migration'lar düz SQL olarak tutulur, ORM'den üretilmez.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, pg_enum, ts_now, ts_optional, uuid_fk, uuid_pk

# Şemadaki `vector(1024)` ile eşleşmek zorunda (0001_core_schema.sql): sayı burada
# değişirse indeks anlamsızlaşır. Üretim modeli bge-m3 değil
# intfloat/multilingual-e5-large; ikisi de 1024 boyutlu, gerekçe
# modules/ingestion/embedding.py docstring'inde.
EMBEDDING_DIM = 1024


class MembershipRole(StrEnum):
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkContentType(StrEnum):
    TEXT = "text"
    TABLE = "table"
    CODE = "code"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at]


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid_pk]
    code: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid_fk] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[created_at]


class CourseMembership(Base):
    __tablename__ = "course_memberships"

    course_id: Mapped[uuid_fk] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid_fk] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[MembershipRole] = mapped_column(pg_enum(MembershipRole, "membership_role"))
    status: Mapped[MembershipStatus] = mapped_column(
        pg_enum(MembershipStatus, "membership_status"),
        default=MembershipStatus.ACTIVE,
    )
    created_at: Mapped[created_at]


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    uploaded_by: Mapped[uuid_fk] = mapped_column(ForeignKey("profiles.id"))
    file_name: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"), default=DocumentStatus.UPLOADED
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at]
<<<<<<< HEAD
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # Kaynak sürümü (FR-118, 0008). Bağ AÇIK EYLEMLE kurulur: yükleme ucu opsiyonel
    # `replaces_document_id` alır. Dosya adına bakarak otomatik eşleme reddedildi —
    # `file_name` üzerinde tekillik yok ve güvenilmez bir işaret, hiç işaret
    # olmamasından kötüdür. Bayatlık SAKLANMAZ, bu iki kolondan türetilir.
    supersedes_document_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
=======
    updated_at: Mapped[ts_now]
>>>>>>> refactor/modularize


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid_pk]
    # Denormalize: retrieval filtresi JOIN'e bağlı kalmasın.
    course_id: Mapped[uuid_fk] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    document_id: Mapped[uuid_fk] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[ChunkContentType] = mapped_column(
        pg_enum(ChunkContentType, "chunk_content_type"), default=ChunkContentType.TEXT
    )
    language: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[created_at]


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid_pk]
    document_id: Mapped[uuid_fk] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), default=JobStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[ts_optional]
    completed_at: Mapped[ts_optional]
    created_at: Mapped[created_at]
