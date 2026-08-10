"""Kullanıcının kendi profil ve ders üyelikleri sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.core import MembershipRole


class ProfileMembershipOut(BaseModel):
    course_id: UUID
    course_code: str
    course_title: str
    role: MembershipRole


class ProfileOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime
    is_platform_admin: bool
    memberships: list[ProfileMembershipOut]


class ProfileUpdate(BaseModel):
    """Profilde değiştirilebilen tek alan; e-posta kimlik sağlayıcısına aittir."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(max_length=120)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Ad soyad en az 2 karakter olmalı.")
        return normalized
