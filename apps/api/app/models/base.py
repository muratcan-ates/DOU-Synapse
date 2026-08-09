"""SQLAlchemy taban sınıfı ve ortak tipler."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from sqlalchemy import TIMESTAMP, func, text
from sqlalchemy import Enum as SaEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


def pg_enum(enum_cls: type[StrEnum], name: str) -> SaEnum:
    """Değerleri (isimleri değil) kullanan, mevcut PostgreSQL enum tipine bağlanan sütun.

    `create_type=False` kasıtlıdır: enum tipleri migration'larda tanımlanır, ORM
    onları yaratmaya kalkmaz. `values_callable` olmadan SQLAlchemy üye ADLARINI
    (`PENDING`) yazar; şemadaki değerler ise küçük harflidir (`pending`).

    Üç model modülünde de aynı üç satır yazılıydı ve `assessment.py`'deki kopyanın
    docstring'i "core'dan import etmek gereksiz bağımlılık yaratırdı" diyordu.
    Doğru yer üçüncü bir modül değil, hepsinin zaten bağımlı olduğu taban modül:
    `base.py`'yi zaten `Base`, `uuid_pk` ve `created_at` için import ediyorlar
    (Anayasa XI).
    """
    return SaEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        create_type=False,
    )


uuid_pk = Annotated[
    UUID,
    mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
]

uuid_fk = Annotated[UUID, mapped_column(PgUUID(as_uuid=True))]

created_at = Annotated[
    datetime,
    mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
]
