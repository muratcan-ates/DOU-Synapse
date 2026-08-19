"""`core.pagination.paginate` yardımcısının doğrudan birim testleri.

HTTP testleri (test_courses, test_documents_api) dansı uçtan uca çiviler; burada
yardımcının kendi sözleşmesi veritabanısız doğrulanır: `limit + 1` isteme,
dilimleme, imleç üretimi, bozuk imlecin sorgu koşmadan reddi ve `scalars=False`
yolunda imlecin Row'un ilk kolonundan türetilmesi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Select, select

from app.api.deps import PageParams
from app.core.pagination import (
    InvalidCursorError,
    decode_time_cursor,
    encode_time_cursor,
    paginate,
)
from app.models.core import Course


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> list[Any]:
        return list(self._rows)

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """`execute` edilen sorguyu kaydeder ve önceden verilen satırları döndürür."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.executed: list[Select[Any]] = []

    async def execute(self, query: Select[Any]) -> _FakeResult:
        self.executed.append(query)
        return _FakeResult(self._rows)


def _row(minutes_ago: int) -> SimpleNamespace:
    return SimpleNamespace(
        created_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC) - timedelta(minutes=minutes_ago),
        id=uuid4(),
    )


class TestPaginate:
    async def test_fazla_satir_varsa_dilimler_ve_son_gorunenden_imlec_uretir(self) -> None:
        rows = [_row(0), _row(1), _row(2)]
        session = _FakeSession(rows)

        page = await paginate(
            session,  # type: ignore[arg-type]
            select(Course),
            model=Course,
            page=PageParams(limit=2, cursor=None),
        )

        assert page.rows == rows[:2]
        assert page.next_cursor is not None
        assert decode_time_cursor(page.next_cursor) == (rows[1].created_at, rows[1].id)
        # Dans `limit + 1` satır ister ve DESC, DESC sıralar; sorgu bunu taşımalı.
        sql = str(session.executed[0].compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 3" in sql
        assert "ORDER BY courses.created_at DESC, courses.id DESC" in sql

    async def test_fazla_satir_yoksa_imlec_uretmez(self) -> None:
        rows = [_row(0), _row(1)]
        session = _FakeSession(rows)

        page = await paginate(
            session,  # type: ignore[arg-type]
            select(Course),
            model=Course,
            page=PageParams(limit=2, cursor=None),
        )

        assert page.rows == rows
        assert page.next_cursor is None

    async def test_imlec_verilince_tuple_filtresi_eklenir(self) -> None:
        anchor = _row(0)
        session = _FakeSession([])

        await paginate(
            session,  # type: ignore[arg-type]
            select(Course),
            model=Course,
            page=PageParams(limit=2, cursor=encode_time_cursor(anchor.created_at, anchor.id)),
        )

        sql = str(session.executed[0])
        assert "(courses.created_at, courses.id) <" in sql

    async def test_bozuk_imlec_sorgu_kosmadan_reddedilir(self) -> None:
        session = _FakeSession([])

        with pytest.raises(InvalidCursorError):
            await paginate(
                session,  # type: ignore[arg-type]
                select(Course),
                model=Course,
                page=PageParams(limit=2, cursor="bozuk"),
            )

        assert session.executed == []

    async def test_scalars_false_imleci_row_un_ilk_kolonundan_turetir(self) -> None:
        entities = [_row(0), _row(1), _row(2)]
        rows = [(entity, "instructor") for entity in entities]
        session = _FakeSession(rows)

        page = await paginate(
            session,  # type: ignore[arg-type]
            select(Course),
            model=Course,
            page=PageParams(limit=2, cursor=None),
            scalars=False,
        )

        assert page.rows == rows[:2]
        assert page.next_cursor is not None
        assert decode_time_cursor(page.next_cursor) == (entities[1].created_at, entities[1].id)
