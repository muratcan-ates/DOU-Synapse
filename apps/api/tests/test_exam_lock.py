"""Yürüyen sınav oturumu asistanı kapatır — 002 US1 / FR-101…FR-106.

Kapatılan açık: mod politikaları (`exam` modunda ipucu 403) uçlarda zorlanıyordu
ama sınav **durumu** hiçbir yerde okunmuyordu. `exam_sessions.mode` sütunu
`api/exams.py` dışında hiçbir dosyada geçmiyordu. Sonuç: öğrenci sınavı başlatıp
ikinci sekmede `/chat`'e `mode=qa` ile sınav sorusunu yazıyor ve tam, atıflı
cevabı 200 ile alıyordu. `curl` bile gerekmiyordu — gezinme çubuğu "Asistan"
sekmesini koşulsuz çiziyordu.

**Sekizinci test bir karşı kontroldür ve dosyanın en önemli parçasıdır.** Yedi
testin 403 görmesi tek başına kilidin çalıştığını KANITLAMAZ: fikstür bozuksa
(sınav hiç başlamamışsa, öğrenci derse üye değilse, hat takılı değilse) istek
başka bir sebeple de düşebilir ve testler yine yeşil görünür. Sekizinci test
kilidi monkeypatch ile devre dışı bırakıp **aynı kurulumun 200 + kaynaklı cevap**
ürettiğini gösterir; ancak o zaman 403'ün sebebi kilittir.

Bu, deponun kurulu yöntemi: `test_isolation_layers.py` RLS politikasını bilerek
bozup sızıntının gerçekleştiğini gösteriyor, `rls_isolation_mutation_check.sh`
aynı şeyi 52 mutasyonla yapıyor. Geçen bir test, ancak kırılabildiği
gösterildiğinde bir şey söyler.

Kurulum (`build_course`, `start`, `rewind`) ve hat sahtesi (`Pipeline`,
`sourced_answer`) `tests/factories.py`'den gelir; üçüncü bir kopya kurulum
yazılmaz (Anayasa XI).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.chat import set_pipeline
from app.contracts import RetrievedChunk
from app.modules.assessment import exam_state
from tests.conftest import UserFactory
from tests.factories import (
    EXAM_DURATION_SECONDS,
    BlockingGenerator,
    ExamFixture,
    FakeCitationGuardrail,
    Pipeline,
    build_course,
    install_pipeline,
    make_chunk,
    rewind,
    sourced_answer,
    start,
)

CHAT_QUESTION = "Deadlock'un dört koşulu nedir?"


@pytest.fixture(autouse=True)
def pipeline() -> Iterator[Pipeline]:
    """Sohbet hattı takılı; kilit olmasaydı her istek 200 dönerdi.

    `autouse` çünkü bu dosyadaki her test, kilidin **cevap verebilecek** bir
    hattı kapattığını göstermek zorunda. Hat takılı olmasaydı uç 503 dönerdi ve
    testler kilidi değil eksik kurulumu ölçerdi (`api/chat.py` fail-closed).
    """
    from app.api.chat import reset_rate_limit, set_pipeline

    fake = Pipeline()
    install_pipeline(fake)
    reset_rate_limit()
    yield fake
    set_pipeline()
    reset_rate_limit()


def _serve_answer(pipeline: Pipeline, course_id: str) -> RetrievedChunk:
    chunk = pipeline.serve(course_id, make_chunk())
    pipeline.answers(sourced_answer(chunk))
    return chunk


async def _ask(
    client: AsyncClient, fixture: ExamFixture, *, mode: str = "qa", headers: Any = None
) -> Any:
    return await client.post(
        f"/courses/{fixture.course_id}/chat",
        json={"question": CHAT_QUESTION, "mode": mode},
        headers=headers or fixture.student,
    )


async def _locked_fixture(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    pipeline: Pipeline,
    *,
    mode: str = "exam",
) -> tuple[ExamFixture, str]:
    """Ders + cevap verebilir hat + başlatılmış oturum."""
    fixture = await build_course(client, users, admin_engine)
    _serve_answer(pipeline, fixture.course_id)
    body = await start(client, fixture, mode)
    return fixture, body["id"]


class TestKilitYururken:
    async def test_qa_modu_reddedilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """FR-101: sınav sürerken normal sohbet kapalı."""
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)

        response = await _ask(client, fixture)

        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == exam_state.EXAM_LOCK_REASON
        assert "sınav" in response.json()["error"]["message"].lower()

    async def test_socratic_modu_da_reddedilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """FR-102: Sokratik merdivenin kaynaklı açıklama kademesi de bir yardım yüzeyi.

        Kural mod eksenine değil durum eksenine yazıldığı için tek bir mod açık
        bırakılamaz; açık bırakılsaydı öğrenci `socratic` ile beşinci kademeye
        çıkıp kaynaklı açıklamayı alırdı.
        """
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)

        response = await _ask(client, fixture, mode="socratic")

        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == exam_state.EXAM_LOCK_REASON

    async def test_gecmis_okuma_yuzeyleri_de_kapali(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """İkinci sekme yolu: geçmiş, önceki turların atıflı cevaplarını taşıyor.

        Yalnız `POST /chat` kapatılsaydı kilit buradan delinirdi — öğrenci sınav
        öncesi sorduğu soruların kaynaklı cevaplarını sınav sırasında okurdu.
        """
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)

        listing = await client.get(
            f"/courses/{fixture.course_id}/chat/sessions", headers=fixture.student
        )
        messages = await client.get(
            f"/courses/{fixture.course_id}/chat/sessions/{UUID(int=0)}",
            headers=fixture.student,
        )

        assert listing.status_code == 403, listing.text
        assert messages.status_code == 403, messages.text

    async def test_yoklama_ucu_kilitliyken_de_cevap_verir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """Arayüz kilidin sebebini öğrenebilmeli; yoksa 'bir şeyler ters gitti' der."""
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)

        response = await client.get(
            f"/courses/{fixture.course_id}/chat/availability", headers=fixture.student
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["available"] is False
        assert body["reason"] == exam_state.EXAM_LOCK_REASON
        assert body["message"] == exam_state.EXAM_LOCK_MESSAGE

    async def test_sohbet_sururken_baslayan_sinav_cevabi_geri_dondurmez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """Forced interleaving: chat starts, exam commits, chat must reject."""

        fixture = await build_course(client, users, admin_engine)
        chunk = pipeline.serve(fixture.course_id, make_chunk())
        entered_provider = asyncio.Event()
        release_provider = asyncio.Event()

        set_pipeline(
            retriever_factory=lambda _session: pipeline.retriever,
            generator=BlockingGenerator(chunk, entered=entered_provider, release=release_provider),
            guardrails=[FakeCitationGuardrail()],
        )
        chat_task = asyncio.create_task(_ask(client, fixture))
        await asyncio.wait_for(entered_provider.wait(), timeout=2)

        exam = await start(client, fixture, "exam")
        release_provider.set()
        chat = await chat_task

        assert exam["mode"] == "exam"
        assert chat.status_code == 403, chat.text
        assert chat.json()["error"]["code"] == exam_state.EXAM_LOCK_REASON
        async with admin_engine.connect() as connection:
            artifact_counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM chat_sessions "
                        " WHERE course_id=:course_id AND user_id=:user_id), "
                        "(SELECT count(*) FROM request_logs "
                        " WHERE course_id=:course_id AND user_id=:user_id)"
                    ),
                    {
                        "course_id": UUID(fixture.course_id),
                        "user_id": fixture.student_id,
                    },
                )
            ).one()
        assert tuple(artifact_counts) == (0, 0)


class TestKilidinKapsami:
    """Kilit fazla kapatmamalı. Bu sınıf 'ne kapanmıyor'u ölçer."""

    async def test_suresi_dolan_oturum_kilitlemez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """FR-104: kilit 'bitmemiş oturum'a değil 'yürüyen oturum'a bağlı.

        Öğrenci sınav sekmesini kapatıp gitse oturum `finished_at IS NULL` olarak
        kalır. Kilit ona bağlansaydı asistan kalıcı olarak kapanırdı.
        """
        fixture, session_id = await _locked_fixture(client, users, admin_engine, pipeline)
        await rewind(admin_engine, session_id, minutes=EXAM_DURATION_SECONDS // 60 + 1)

        response = await _ask(client, fixture)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "answered"

    async def test_practice_modu_kilitlemez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """Prova modu yardımı kapatmaz — orada ipucu zaten açık (exams.py mod tablosu)."""
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline, mode="practice")

        response = await _ask(client, fixture)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "answered"

    async def test_egitmen_etkilenmez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """FR-103: kilit değerlendirilen kişiyi hedefler.

        Eğitmenin kendi dersinde açtığı bir sınav oturumu onu asistandan mahrum
        bırakmamalı. Muafiyet sunucuda ve ilk satırda; istemcide tekrarlanmıyor.
        """
        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)

        response = await _ask(client, fixture, headers=fixture.instructor)

        assert response.status_code == 200, response.text

    async def test_sinav_bitince_asistan_geri_acilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        """Şartnamenin Independent Test'i: kilit kalıcı değil, duruma bağlı."""
        fixture, session_id = await _locked_fixture(client, users, admin_engine, pipeline)
        assert (await _ask(client, fixture)).status_code == 403

        finish = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )
        assert finish.status_code == 200, finish.text

        response = await _ask(client, fixture)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "answered"


class TestKarsiKontrol:
    """FR-106 — testin kırılabildiğinin kanıtı."""

    async def test_kilit_devre_disiyken_ayni_kurulum_cevap_uretir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Kilit kaldırılınca 403 kaybolur ve kaynaklı cevap geri gelir.

        Bu test yeşil kalıyor ama yukarıdaki yedisi de yeşilse, 403'ün sebebi
        kilit DEĞİL başka bir şeydir (bozuk fikstür, üyelik hatası, takılı olmayan
        hat) ve kilit hiçbir şey kanıtlamıyordur.

        `deps.py` modülü `exam_state.active_exam_session(...)` diye çağırıyor,
        `from ... import` ile bağlanmış bir kopya üzerinden değil; bu yüzden tek
        attribute'u değiştirmek kilidi gerçekten devre dışı bırakır. Çağrı
        biçimi değişirse bu patch sessizce etkisiz kalır ve test yanlış bir
        güven verir — çağrının modül üzerinden yapılması bu yüzden bir kuraldır.
        """

        async def _hep_none(*_args: Any, **_kwargs: Any) -> None:
            return None

        fixture, _ = await _locked_fixture(client, users, admin_engine, pipeline)
        monkeypatch.setattr(exam_state, "active_exam_session", _hep_none)

        response = await _ask(client, fixture)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "answered"
        assert body["citations"], "kilit kalkınca kaynaklı cevap dönmeli"
