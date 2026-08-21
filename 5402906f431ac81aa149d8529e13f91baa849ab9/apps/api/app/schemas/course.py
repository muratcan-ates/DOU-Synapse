"""Ders ve üyelik API sözleşmeleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.core import MembershipRole, MembershipStatus


class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32, examples=["COME301"])
    title: str = Field(min_length=2, max_length=200, examples=["İşletim Sistemleri"])


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    created_at: datetime


class CourseWithRole(CourseOut):
    """Listelemede kullanıcının o dersteki rolü de döner."""

    role: MembershipRole


class MembershipCreate(BaseModel):
    email: EmailStr = Field(description="Derse eklenecek kullanıcının e-posta adresi")
    role: MembershipRole = MembershipRole.STUDENT


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    full_name: str | None
    role: MembershipRole
    status: MembershipStatus
