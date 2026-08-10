"""Belge yükleme ve durum uçları."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status
from sqlalchemy import select, text, tuple_
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    CourseInstructorDep,
    CourseMemberDep,
    PageDep,
    SessionDep,
    SettingsDep,
)
from app.core.db import db_now
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.pagination import decode_time_cursor, encode_time_cursor
from app.models.core import Chunk, Document, DocumentStatus
from app.modules.ingestion.storage import get_storage
from app.modules.ingestion.validation import validate_upload
from app.schemas.document import ChunkPreview, DocumentOut, DocumentUploadOut
from app.schemas.page import PageOut

router = APIRouter(prefix="/courses/{course_id}/documents", tags=["documents"])
logger = get_logger("app.documents")


async def _trigger_worker() -> None:
    """Worker'ı bir tur çalıştırır.

    Yükleme yanıtı istemciye döndükten sonra çalışır; böylece kullanıcı belgenin
    işlenmesini beklemez. Bulutta bu tetik worker servisine HTTP çağrısına dönüşür
    (ARCHITECTURE.md §1) — çağıran kod aynı kalır, seçimi `trigger_drain` yapar.
    """
    from app.api.internal import trigger_drain

    await trigger_drain()


@router.post("", response_model=DocumentUploadOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    context: CourseInstructorDep,
    session: SessionDep,
    settings: SettingsDep,
    background: BackgroundTasks,
    file: UploadFile = File(description="PDF, PPTX, Markdown, metin veya kod dosyası"),
    replaces_document_id: Annotated[
        UUID | None,
        Form(description="Bu yüklemenin açıkça yerine geçtiği eski belge kimliği"),
    ] = None,
) -> DocumentUploadOut:
    """Ders materyali yükler ve işleme kuyruğuna alır.

    Dosya diske yazılmadan önce uzantı, boyut ve sihirli baytlarıyla doğrulanır; depolama
    anahtarı sunucuda üretilir, kullanıcının verdiği ad hiçbir zaman yol olarak
    kullanılmaz.
    """
    if not file.filename:
        raise ValidationError("Dosya adı okunamadı.")

    content = await file.read()
    upload = validate_upload(
        file_name=file.filename,
        content=content,
        course_id=str(context.course_id),
        allowed_extensions=settings.allowed_upload_extensions,
        max_bytes=settings.max_upload_bytes,
    )

    existing = (
        await session.execute(
            select(Document).where(
                Document.course_id == context.course_id,
                Document.file_hash == upload.sha256,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Aynı içerik yeniden embed edilmez; boşuna işlem ve maliyet oluşmaz.
        raise ConflictError(f"Bu dosya derse zaten yüklenmiş: {existing.file_name}")

    replaced: Document | None = None
    if replaces_document_id is not None:
        replaced = await session.get(Document, replaces_document_id)
        if replaced is None or replaced.course_id != context.course_id:
            raise NotFoundError("Yerine geçilecek belge bu derste bulunamadı.")
        if replaced.superseded_at is not None:
            raise ConflictError(
                "Bu belgenin yerine daha önce yeni bir sürüm yüklenmiş. "
                "Zincirin en güncel belgesini seçin."
            )

    storage = get_storage()
    await storage.save(upload.storage_key, upload.content)

    document = Document(
        course_id=context.course_id,
        uploaded_by=context.user_id,
        file_name=upload.original_name,
        file_type=upload.extension,
        storage_path=upload.storage_key,
        file_hash=upload.sha256,
        byte_size=upload.byte_size,
        status=DocumentStatus.UPLOADED,
        supersedes_document_id=replaced.id if replaced else None,
    )
    session.add(document)
    if replaced is not None:
        replaced.superseded_at = await db_now(session)
    await session.flush()

    await session.execute(
        text("INSERT INTO ingestion_jobs (document_id) VALUES (:document_id)"),
        {"document_id": document.id},
    )

    background.add_task(_trigger_worker)

    return DocumentUploadOut(document=DocumentOut.model_validate(document))


@router.get("", response_model=PageOut[DocumentOut])
async def list_documents(
    context: CourseMemberDep,
    session: SessionDep,
    page: PageDep,
) -> PageOut[DocumentOut]:
    query = select(Document).where(Document.course_id == context.course_id)
    if page.cursor is not None:
        created_at, row_id = decode_time_cursor(page.cursor)
        query = query.where(tuple_(Document.created_at, Document.id) < (created_at, row_id))
    result = await session.execute(
        query.order_by(Document.created_at.desc(), Document.id.desc()).limit(page.limit + 1)
    )
    rows = list(result.scalars())
    visible = rows[: page.limit]
    next_cursor = (
        encode_time_cursor(visible[-1].created_at, visible[-1].id)
        if len(rows) > page.limit
        else None
    )
    return PageOut(
        items=[DocumentOut.model_validate(doc) for doc in visible], next_cursor=next_cursor
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID, context: CourseMemberDep, session: SessionDep
) -> DocumentOut:
    document = await session.get(Document, document_id)
    # RLS başka dersin belgesini zaten gizler; yine de ders eşleşmesi açıkça kontrol
    # edilir — iki katman da bağımsız olarak doğru davranmalı.
    if document is None or document.course_id != context.course_id:
        raise NotFoundError("Belge bulunamadı.")
    return DocumentOut.model_validate(document)


@router.post("/{document_id}/retry", response_model=DocumentOut)
async def retry_document(
    document_id: UUID,
    context: CourseInstructorDep,
    session: SessionDep,
    background: BackgroundTasks,
) -> DocumentOut:
    """Kalıcı hataya düşen ingestion işini eğitmen açıkça yeniden kuyruğa alır."""
    document = await session.get(Document, document_id)
    if document is None or document.course_id != context.course_id:
        raise NotFoundError("Belge bulunamadı.")
    if document.status != DocumentStatus.FAILED:
        raise ConflictError("Yalnız başarısız bir belge yeniden işlenebilir.")

    result = await session.execute(
        text("SELECT app.retry_ingestion_job(:document_id)"),
        {"document_id": document.id},
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Belgenin işleme kaydı bulunamadı.")

    document.status = DocumentStatus.UPLOADED
    document.error_message = None
    await session.flush()
    background.add_task(_trigger_worker)
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/chunks", response_model=list[ChunkPreview])
async def preview_chunks(
    document_id: UUID,
    context: CourseInstructorDep,
    session: SessionDep,
    limit: int = 20,
) -> list[ChunkPreview]:
    """Eğitmenin, belgeden ne çıkarıldığını görmesi için ilk chunk'lar."""
    document = await session.get(Document, document_id)
    if document is None or document.course_id != context.course_id:
        raise NotFoundError("Belge bulunamadı.")

    result = await session.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
        .limit(min(max(limit, 1), 100))
    )
    return [
        ChunkPreview(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            slide_number=chunk.slide_number,
            section_title=chunk.section_title,
            content_type=chunk.content_type.value,
            token_count=chunk.token_count,
            text=chunk.text,
        )
        for chunk in result.scalars()
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> None:
    """Belgeyi ve ona bağlı tüm chunk'ları siler.

    Chunk'lar FK cascade ile gider: materyal kaldırıldığında ondan üretilmiş vektörlerin
    aramada kalmaması, "yalnızca yüklenen materyalden cevap" garantisinin parçasıdır.

    Ama cascade her yere ulaşmaz: `questions.source_chunk_id` `ON DELETE RESTRICT`
    taşır, yani o chunk'tan üretilmiş bir soru havuzdaysa silme veritabanı düzeyinde
    reddedilir. Bu kısıt bilinçlidir — kaynağı silinmiş bir soru, kaynağına karşı
    doğrulanamayan bir sorudur (Anayasa I). Kısıtı gevşetmek yerine hatayı çeviriyoruz.
    """
    document = await session.get(Document, document_id)
    if document is None or document.course_id != context.course_id:
        raise NotFoundError("Belge bulunamadı.")

    storage_key = document.storage_path
    await session.delete(document)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Şerit 4 teşhis etti: soru üretimi inince bu yol ULAŞILABİLİR hâle geldi ve
        # kullanıcı 409 yerine 500 görüyordu — yani "yapamazsın, şu yüzden" yerine
        # "bir şeyler ters gitti". Kısıtın kendisi doğru, mesajı yoktu.
        raise ConflictError(
            "Bu belgeden üretilmiş sorular havuzda olduğu için belge silinemiyor. "
            "Önce ilgili soruları kaldırın."
        ) from exc

    # Depodaki dosya en sona bırakılır: satır silinemezse dosya da durmalı, yoksa
    # veritabanında kaydı olan ama dosyası olmayan bir belge kalırdı.
    await get_storage().delete(storage_key)
