"""Yeni taslak yazımlarının doğrulaması; eski soru okuma şemaları değişmez."""

from __future__ import annotations

from typing import Any, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.assessment import LearningOutcome, QuestionType
from app.models.core import Chunk
from app.schemas.assessment import (
    AnswerFormat,
    BugHuntPayload,
    CodeTracePayload,
    McqPayload,
    OpenPayload,
    parse_payload,
    validate_new_code_rubric,
)


async def load_classification(
    session: AsyncSession, *, course_id: UUID, topic_id: UUID, outcome_id: UUID | None
) -> LearningOutcome | None:
    if outcome_id is None:
        return None
    outcome = await session.get(LearningOutcome, outcome_id)
    if outcome is None or outcome.course_id != course_id:
        raise NotFoundError("Öğrenme çıktısı bulunamadı.")
    if outcome.topic_id is not None and outcome.topic_id != topic_id:
        raise ValidationError("Öğrenme çıktısı sorunun konusuyla eşleşmeli.")
    return outcome


def _check_fields(
    raw: Any, parsed: Any, original: Any, *, item_model: type[BaseModel] | None = None
) -> None:
    """Bilinmeyen eski metadata korunur, yeni metadata yazma kanalı açılamaz."""
    if isinstance(parsed, BaseModel) and isinstance(raw, dict):
        original = original if isinstance(original, dict) else {}
        for key in set(raw) - set(type(parsed).model_fields):
            if key not in original or raw[key] != original[key]:
                raise ValidationError("Soru içeriğinde tanınmayan alan değiştirilemez.")
        for key, field in type(parsed).model_fields.items():
            # Omitted optional lists still parse to defaults; validate them too,
            # or dropping a rubric could erase metadata without entering the loop.
            annotation = field.annotation
            child_model = None
            if get_origin(annotation) is list:
                candidate = get_args(annotation)[0]
                if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                    child_model = candidate
            _check_fields(
                raw.get(key, getattr(parsed, key)),
                getattr(parsed, key),
                original.get(key),
                item_model=child_model,
            )
    elif isinstance(parsed, list) and isinstance(raw, list):
        original = original if isinstance(original, list) else []
        if item_model is not None and any(
            isinstance(item, dict) and set(item) - set(item_model.model_fields) for item in original
        ):
            # Bu eski satırlarda metadata için kalıcı satır kimliği yoktur.
            # Listeyi kısaltıp metadata'yı indekse göre kopyalamak başka bir
            # ölçüte ait veriyi sessizce yeniden atardı. Belirsizlikte kapat.
            identity = "key" if "key" in item_model.model_fields else "point"
            if len(original) != len(parsed) or any(
                not isinstance(old, dict) or old.get(identity) != getattr(new, identity)
                for old, new in zip(original, parsed, strict=True)
            ):
                raise ValidationError(
                    "Eski ek alanları olan listede satır sayısı, sırası ve adı değiştirilemez."
                )
        for index, (raw_item, parsed_item) in enumerate(zip(raw, parsed, strict=True)):
            _check_fields(raw_item, parsed_item, original[index] if index < len(original) else None)
    elif isinstance(parsed, str) and not parsed.strip():
        raise ValidationError("Soru içeriğindeki metin alanları boş bırakılamaz.")


def _preserve_metadata(parsed: Any, cleaned: Any, original: Any) -> Any:
    if isinstance(parsed, BaseModel) and isinstance(original, dict):
        for key, value in original.items():
            if key not in type(parsed).model_fields:
                cleaned[key] = value
            elif key in cleaned:
                cleaned[key] = _preserve_metadata(getattr(parsed, key), cleaned[key], value)
    elif isinstance(parsed, list) and isinstance(original, list):
        for index, value in enumerate(original[: len(parsed)]):
            cleaned[index] = _preserve_metadata(parsed[index], cleaned[index], value)
    return cleaned


async def validate_draft_payload(
    session: AsyncSession,
    *,
    question_type: QuestionType,
    raw: dict[str, Any],
    original: dict[str, Any],
    course_id: UUID,
) -> dict[str, Any]:
    try:
        parsed = parse_payload(question_type, raw)
    except PydanticValidationError as exc:
        raise ValidationError(
            "Soru içeriği seçili türe uygun değil. "
            "Metni, cevap anahtarını ve ölçütleri kontrol edin."
        ) from exc
    _check_fields(raw, parsed, original)
    if isinstance(parsed, McqPayload):
        source_ids = set(parsed.distractor_sources.values())
        available = set(
            await session.scalars(
                select(Chunk.id).where(Chunk.course_id == course_id, Chunk.id.in_(source_ids))
            )
        )
        if source_ids != available:
            raise ValidationError("Çeldirici kaynakları bu dersin kaynaklarından seçilmeli.")
    if isinstance(parsed, OpenPayload):
        for value in [*parsed.key_points, *parsed.accepted_answers]:
            if not value.strip() or len(value) > 1000:
                raise ValidationError(
                    "Anahtar noktalar ve kabul edilen cevaplar 1-1000 karakter olmalı."
                )
        if parsed.format is AnswerFormat.ESSAY:
            if not parsed.rubric or sum(item.weight for item in parsed.rubric) != 100:
                raise ValidationError(
                    "Klasik soruda değerlendirme ölçütlerinin toplamı 100 olmalı."
                )
    if isinstance(parsed, (CodeTracePayload, BugHuntPayload)):
        try:
            validate_new_code_rubric(parsed.rubric)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
    return _preserve_metadata(parsed, parsed.model_dump(mode="json"), original)
