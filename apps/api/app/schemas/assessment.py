"""Ölçme (assessment) API sözleşmeleri.

Yalnızca T030'un `topics` ucu için gereken şemalar burada. Soru/sınav/mastery şemaları
sonraki teslimatlarda (T029, T030'un kalanı, T032, T038) bu dosyaya eklenir.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200, examples=["Deadlock"])


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    name: str
    created_by: UUID
    created_at: datetime
