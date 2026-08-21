"""SQLAlchemy taban sınıfı ve ortak tipler."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from sqlalchemy import TIMESTAMP, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


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
