"""Kaynak bağlamı ve öğretmen retrieval laboratuvarı API testleri."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import sources as source_api
from app.contracts import RetrievedChunk
from app.modules.retrieval.inspection import RetrievalInspection
from app.modules.retrieval.scope import EvidenceLevel, EvidenceVerdict
from tests.conftest import UserFactory
from tests.factories import build_course, start
from tests.factories import create_course as _create_course
from tests.factories import enroll_student as _add_student


def _candidate(*, dense: float = 0.92) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name="05-deadlock.pdf",
        page_number=7,
        slide_number=None,
        section_title="Coffman koşulları",
        text="Deadlock için dört Coffman koşulu aynı anda sağlanmalıdır.",
        dense_score=dense,
        fts_score=0.08,
        fused_score=0.03,
    )


class TestRetrievalLaboratuvari:
    async def test_egitmen_ham_adaylari_ve_kanit_kararini_gorur(
        self,
        client: AsyncClient,
        users: UserFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        instructor = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, instructor, "COME301")
        candidate = _candidate()

        async def fake_inspect(*_args: object, **_kwargs: object) -> RetrievalInspection:
            return RetrievalInspection(
                query="Deadlock koşulları",
                candidates=[candidate],
                verdict=EvidenceVerdict(
                    level=EvidenceLevel.SUFFICIENT,
                    best_dense_score=candidate.dense_score,
                    best_fts_score=candidate.fts_score,
                    lexical_coverage=0.5,
                    threshold=0.81,
                ),
            )

        monkeypatch.setattr(source_api, "inspect_retrieval", fake_inspect)
        response = await client.post(
            f"/courses/{course_id}/sources/inspect",
            json={"query": "Deadlock koşulları", "limit": 8},
            headers=instructor,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["level"] == "sufficient"
        assert body["answer_allowed"] is True
        assert body["threshold"] == pytest.approx(0.81)
        assert body["candidate_count"] == 1
        assert body["candidates"][0] == {
            "rank": 1,
            "chunk_id": str(candidate.chunk_id),
            "document_id": str(candidate.document_id),
            "file_name": "05-deadlock.pdf",
            "location": "Sayfa 7",
            "text": candidate.text,
            "dense_score": pytest.approx(0.92),
            "fts_score": pytest.approx(0.08),
            "fused_score": pytest.approx(0.03),
        }

    async def test_ogrenci_retrieval_laboratuvarini_kullanamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        instructor = users.auth(await users.create("ayse@dogus.edu.tr"))
        student_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, instructor, "COME301")
        await _add_student(client, instructor, course_id, "burak@dogus.edu.tr")

        response = await client.post(
            f"/courses/{course_id}/sources/inspect",
            json={"query": "Deadlock koşulları"},
            headers=users.auth(student_id),
        )

        assert response.status_code == 403


class TestKaynakBaglami:
    async def test_ogrenci_atif_parcasini_komsulariyla_gorur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        selected = fixture.chunk_ids[1]

        response = await client.get(
            f"/courses/{fixture.course_id}/sources/{selected}", headers=fixture.student
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["selected_chunk_id"] == str(selected)
        assert len(body["chunks"]) == 2
        assert [chunk["chunk_index"] for chunk in body["chunks"]] == [0, 1]
        assert [chunk["selected"] for chunk in body["chunks"]] == [False, True]
        assert all(chunk["text"] for chunk in body["chunks"])

    async def test_bosluk_sorgusu_retrieval_calistirmadan_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        instructor = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, instructor, "COME301")

        response = await client.post(
            f"/courses/{course_id}/sources/inspect",
            json={"query": "   "},
            headers=instructor,
        )

        assert response.status_code == 422

    async def test_uye_olmayan_kaynak_kimligini_deneyemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        outsider = users.auth(await users.create("ceren@dogus.edu.tr"))

        response = await client.get(
            f"/courses/{fixture.course_id}/sources/{fixture.chunk_ids[0]}", headers=outsider
        )

        assert response.status_code == 404

    async def test_baska_ders_yolunda_chunk_gizlenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        other_course = await _create_course(client, fixture.instructor, "COME302")

        response = await client.get(
            f"/courses/{other_course}/sources/{fixture.chunk_ids[0]}",
            headers=fixture.instructor,
        )

        assert response.status_code == 404

    async def test_aktif_sinavda_ogrenci_kaynagi_acamaz_egitmen_acar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")
        path = f"/courses/{fixture.course_id}/sources/{fixture.chunk_ids[0]}"

        student = await client.get(path, headers=fixture.student)
        instructor = await client.get(path, headers=fixture.instructor)

        assert student.status_code == 403
        assert student.json()["error"]["code"] == "exam_in_progress"
        assert instructor.status_code == 200

    async def test_olmayan_chunk_404(self, client: AsyncClient, users: UserFactory) -> None:
        instructor = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, instructor, "COME301")

        response = await client.get(f"/courses/{course_id}/sources/{uuid4()}", headers=instructor)

        assert response.status_code == 404
