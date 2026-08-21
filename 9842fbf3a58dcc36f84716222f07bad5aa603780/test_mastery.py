"""Mastery-Lite testleri (T039).

tasks.md'deki dört vaka: EWMA hesabı, ipucu çarpanları, seviye sınır değerleri (0.40 ve
0.75 tam sınırda), ilk cevapta başlangıç davranışı. Bu dördü saf fonksiyonlar üzerinde
(`compute_new_score`, `level_for`) test edilir — veritabanı gerektirmezler, hızlıdır.
Ayrıca `record_answer`'ın gerçek bir RLS oturumunda satır yazdığını doğrulayan bir
entegrasyon testi eklenmiştir (Anayasa VIII: davranış gerçek ortamda gözlenmeli).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import rls_session
from app.modules.mastery.service import (
    HINT_MULTIPLIERS,
    MasteryLevel,
    compute_new_score,
    level_for,
    record_answer,
)
from tests.conftest import UserFactory


class TestEwmaCalculation:
    def test_sonraki_skor_agirlikli_ortalama(self) -> None:
        # yeni = 0.7 * eski + 0.3 * son ; eski=0.60, raw=100, hint=0 -> son=1.00
        new_score = compute_new_score(
            previous_score=0.60, previous_answer_count=3, raw_score=100, hint_level=0
        )
        assert new_score == pytest.approx(0.7 * 0.60 + 0.3 * 1.00)

    def test_dusuk_skor_ortalamayi_asagi_ceker(self) -> None:
        new_score = compute_new_score(
            previous_score=0.80, previous_answer_count=5, raw_score=0, hint_level=0
        )
        assert new_score == pytest.approx(0.7 * 0.80 + 0.3 * 0.0)


class TestHintMultipliers:
    def test_carpan_tablosu_spesifikasyonla_birebir(self) -> None:
        assert HINT_MULTIPLIERS == {0: 1.00, 1: 0.85, 2: 0.70, 3: 0.50, 4: 0.25}

    @pytest.mark.parametrize(
        ("hint_level", "multiplier"),
        [(0, 1.00), (1, 0.85), (2, 0.70), (3, 0.50), (4, 0.25)],
    )
    def test_carpan_ewma_oncesi_ham_skora_uygulanir(
        self, hint_level: int, multiplier: float
    ) -> None:
        # İlk cevap (previous_answer_count=0): yeni = son = raw/100 * carpan.
        new_score = compute_new_score(
            previous_score=None,
            previous_answer_count=0,
            raw_score=100,
            hint_level=hint_level,
        )
        assert new_score == pytest.approx(multiplier)


class TestLevelThresholds:
    def test_tam_040_ortaya_girer(self) -> None:
        assert level_for(0.40) is MasteryLevel.MEDIUM

    def test_040_altinda_gelistirilmeli(self) -> None:
        assert level_for(0.399) is MasteryLevel.NEEDS_WORK

    def test_tam_075_iyiye_girer(self) -> None:
        assert level_for(0.75) is MasteryLevel.GOOD

    def test_075_altinda_orta(self) -> None:
        assert level_for(0.749) is MasteryLevel.MEDIUM


class TestFirstAnswerBehavior:
    def test_ilk_cevapta_070_ile_baslatilmaz(self) -> None:
        """İlk cevap: yeni = son. 0.7*0 + 0.3*son ile başlatılsaydı öğrenci haksız yere
        düşük gösterilirdi — brief bunu açıkça yasaklıyor."""
        new_score = compute_new_score(
            previous_score=None, previous_answer_count=0, raw_score=80, hint_level=0
        )
        assert new_score == pytest.approx(0.80)
        # Yanlış (EWMA'dan 0 ile başlatılan) sonuçtan belirgin şekilde farklı olmalı.
        assert new_score != pytest.approx(0.7 * 0.0 + 0.3 * 0.80)

    def test_ikinci_cevapta_artik_ewma_uygulanir(self) -> None:
        first = compute_new_score(
            previous_score=None, previous_answer_count=0, raw_score=80, hint_level=0
        )
        second = compute_new_score(
            previous_score=first, previous_answer_count=1, raw_score=40, hint_level=0
        )
        assert second == pytest.approx(0.7 * first + 0.3 * 0.40)


class TestRecordAnswerIntegration:
    """record_answer'ın gerçek RLS oturumunda mastery satırı yazdığının kanıtı."""

    async def test_record_answer_satiri_yazar_ve_gunceller(
        self, client: AsyncClient, users: UserFactory, admin_engine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_response = await client.post(
            "/courses", json={"code": "COME301", "title": "İşletim Sistemleri"}, headers=ayse
        )
        course_id = UUID(course_response.json()["id"])
        topic_response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )
        topic_id = UUID(topic_response.json()["id"])

        async with rls_session(ayse_id) as session:
            first_score = await record_answer(
                session,
                user_id=ayse_id,
                topic_id=topic_id,
                course_id=course_id,
                raw_score=80,
                hint_level=0,
            )
        assert first_score == pytest.approx(0.80)

        async with rls_session(ayse_id) as session:
            second_score = await record_answer(
                session,
                user_id=ayse_id,
                topic_id=topic_id,
                course_id=course_id,
                raw_score=40,
                hint_level=1,
            )
        assert second_score == pytest.approx(0.7 * 0.80 + 0.3 * (0.40 * 0.85))

        async with admin_engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT answer_count FROM mastery WHERE user_id = :uid AND topic_id = :tid"
                    ),
                    {"uid": ayse_id, "tid": topic_id},
                )
            ).one()
        assert row.answer_count == 2
