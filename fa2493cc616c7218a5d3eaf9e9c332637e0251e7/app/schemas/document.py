"""Belge API sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.core import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_type: str
    byte_size: int
    status: DocumentStatus
    page_count: int | None
    chunk_count: int
    error_message: str | None
    supersedes_document_id: UUID | None = None
    superseded_at: datetime | None = None
    created_at: datetime


class DocumentUploadOut(BaseModel):
    """Yükleme kabul yanıtı.

    Belge arka planda işlendiği için 202 döner; istemci `status` alanını izleyerek
    ilerlemeyi gösterir.
    """

    document: DocumentOut
    message: str = "Belge alındı ve işleme kuyruğuna eklendi."


class ChunkPreview(BaseModel):
    """Eğitmenin, sistemin belgeden ne çıkardığını görebilmesi için."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    content_type: str
    token_count: int
    text: str
