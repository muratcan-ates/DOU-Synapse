"""Sınav blueprint testleri — 002 US3 (T510).

Kurulum yardımcıları `test_assessment.py`'den devşirilir; ikinci bir kurulum kopyası
yazılmaz (Anayasa XI).

Bu dosyanın kapsadığı iddialar, sırayla: FR-110 (çıktı tanımı ve tekilliği),
FR-112 (dağılımın iç tutarlılığı ve hangi hücrenin tutmadığı), FR-114 (yayın kapısı
ve sınıflandırılmamış kalemin ayrı raporlanması), FR-115 (yayınlanmış sürümün
değişmezliği, dağılımın dondurulması, yürüyen oturumun sürümünü görmeye devam
etmesi), FR-116 (yayın penceresi), FR-119 (onaysız soru kâğıda giremez).

**Yetki testleri ayrı bir sınıfta** (`TestYetkiler`): `data-model.md` §2.13'ün
"sessiz kalabilecek hata" dediği yer burası. REVOKE satırları unutulsa hiçbir
davranış testi kırmızı yanmazdı, çünkü uygulama kodu zaten doğru davranıyor.
O yüzden yetkiyi doğrudan sınayan testler var.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment.grading import _LlmVerdict, _rubric_breakdown
from app.modules.assessment.question_gen import _OpenDraft
from app.schemas.assessment import OpenPayload, RubricItem, normalized_rubric
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    create_course,
    create_topic,
    enroll_student,
    mcq_payload,
    seed_document,
    seed_question,
)


class BlueprintFixture:
    """Bir ders, eğitmen, öğrenci, konu ve sınıflandırılmış onaylı soru havuzu."""

    def __init__(
        self,
        *,
        course_id: str,
        instructor: dict[str, str],
        instructor_id: UUID,
        student: dict[str, str],
        student_id: UUID,
        topic_id: UUID,
        chunk_ids: list[UUID],
    ) -> None:
        self.course_id = course_id
        self.instructor = instructor
        self.instructor_id = instructor_id
        self.student = student
        self.student_id = student_id
        self.topic_id = topic_id
        self.chunk_ids = chunk_ids


async def build(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, *, code: str
) -> BlueprintFixture:
    # Ders kodunda boşluk var ("BP 101") ve e-postaya olduğu gibi geçemez.
    # Alan adı da gerçek olmalı: `.test` özel amaçlı bir TLD ve `EmailStr` reddediyor.
    slug = code.replace(" ", "-").lower()
    instructor_id = await users.create(f"hoca-{slug}@dogus.edu.tr")
    instructor = UserFactory.auth(instructor_id)
    student_id = await users.create(f"ogrenci-{slug}@dogus.edu.tr")
    student = UserFactory.auth(student_id)

    course_id = await create_course(client, instructor, code)
    await enroll_student(client, instructor, course_id, f"ogrenci-{slug}@dogus.edu.tr")
    topic_id = await create_topic(client, instructor, course_id, "Kilitlenme")
    chunk_ids = (
        await seed_document(
            admin_engine,
            course_id=UUID(str(course_id)),
            uploaded_by=instructor_id,
            passages=DEADLOCK_TEXTS,
        )
    ).chunk_ids

    return BlueprintFixture(
        course_id=str(course_id),
        instructor=instructor,
        instructor_id=instructor_id,
        student=student,
        student_id=student_id,
        topic_id=topic_id,
        chunk_ids=chunk_ids,
    )


async def make_outcome(
    client: AsyncClient, fixture: BlueprintFixture, *, code: str, topic: bool = True
) -> UUID:
    response = await client.post(
        f"/courses/{fixture.course_id}/learning-outcomes",
        json={
            "code": code,
            "description": f"{code} kazanımı",
            "topic_id": str(fixture.topic_id) if topic else None,
        },
        headers=fixture.instructor,
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def make_question(
    admin_engine: AsyncEngine,
    fixture: BlueprintFixture,
    *,
    outcome_id: UUID | None,
    difficulty: str | None,
    status: str = "approved",
) -> UUID:
    """Havuza soru yazar ve hücre eksenini atar.

    `seed_question` bu iki kolonu bilmiyor ve o dosya başka şeritlerin de kullandığı
    ortak kurulum; imzasını değiştirmek yerine sınıflandırma burada yapılıyor.
    """
    question_id = await seed_question(
        admin_engine,
        course_id=UUID(fixture.course_id),
        topic_id=fixture.topic_id,
        source_chunk_id=fixture.chunk_ids[0],
        payload=mcq_payload(fixture.chunk_ids),
        question_type=QuestionType.MCQ,
        status=status,
        reviewed_by=fixture.instructor_id if status != "draft" else None,
    )
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE questions SET learning_outcome_id = :outcome, "
                "difficulty = CAST(:difficulty AS question_difficulty) WHERE id = :id"
            ),
            {"outcome": outcome_id, "difficulty": difficulty, "id": question_id},
        )
    return question_id


def cell(
    outcome_id: UUID, *, count: int, points: int = 5, difficulty: str = "easy"
) -> dict[str, Any]:
    return {
        "learning_outcome_id": str(outcome_id),
        "difficulty": difficulty,
        "question_type": "mcq",
        "question_count": count,
        "points_per_question": points,
    }


async def make_blueprint(
    client: AsyncClient,
    fixture: BlueprintFixture,
    *,
    cells: list[dict[str, Any]],
    duration: int = 60,
    max_attempts: int = 1,
    opens_at: str | None = None,
    closes_at: str | None = None,
) -> UUID:
    body: dict[str, Any] = {
        "title": "Vize",
        "duration_minutes": duration,
        "max_attempts": max_attempts,
        "cells": cells,
    }
    if opens_at is not None:
        body["opens_at"] = opens_at
    if closes_at is not None:
        body["closes_at"] = closes_at
    response = await client.post(
        f"/courses/{fixture.course_id}/blueprints", json=body, headers=fixture.instructor
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def make_version(client: AsyncClient, fixture: BlueprintFixture, blueprint_id: UUID) -> UUID:
    response = await client.post(
        f"/courses/{fixture.course_id}/blueprints/{blueprint_id}/versions",
        headers=fixture.instructor,
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def set_items(
    client: AsyncClient,
    fixture: BlueprintFixture,
    blueprint_id: UUID,
    version_id: UUID,
    question_ids: list[UUID],
) -> Any:
    return await client.post(
        f"/courses/{fixture.course_id}/blueprints/{blueprint_id}/versions/{version_id}/items",
        json=[{"question_id": str(qid)} for qid in question_ids],
        headers=fixture.instructor,
    )


async def publish(
    client: AsyncClient, fixture: BlueprintFixture, blueprint_id: UUID, version_id: UUID
) -> Any:
    return await client.post(
        f"/courses/{fixture.course_id}/blueprints/{blueprint_id}/versions/{version_id}/publish",
        headers=fixture.instructor,
    )


# ---------------------------------------------------------------------------


class TestOgrenmeCiktilari:
    """FR-110."""

    async def test_cikti_olusturulur_ve_kod_derste_tekildir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="LO 101")
        await make_outcome(client, fixture, code="CO1")

        ikinci = await client.post(
            f"/courses/{fixture.course_id}/learning-outcomes",
            json={"code": "co1", "description": "Aynı kod, küçük harfle"},
            headers=fixture.instructor,
        )

        assert ikinci.status_code == 409, ikinci.text
        assert "zaten var" in ikinci.json()["error"]["message"]

    async def test_ogrenci_cikti_tanimlayamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="LO 102")

        response = await client.post(
            f"/courses/{fixture.course_id}/learning-outcomes",
            json={"code": "CO1", "description": "Öğrenci denemesi"},
            headers=fixture.student,
        )

        assert response.status_code == 403, response.text


class TestDagilimTutarliligi:
    """FR-112 — tutarsız dağılım kaydedilmez ve HANGİ hücrenin tutmadığı söylenir."""

    async def test_marjinal_tutmayinca_reddedilir_ve_hucre_adlandirilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="BP 101")
        outcome = await make_outcome(client, fixture, code="CO1")

        response = await client.post(
            f"/courses/{fixture.course_id}/blueprints",
            json={
                "title": "Vize",
                "duration_minutes": 60,
                "cells": [cell(outcome, count=3)],
                "targets": {"total_questions": 5, "by_difficulty": {"easy": 5}},
            },
            headers=fixture.instructor,
        )

        assert response.status_code == 422, response.text
        mesaj = response.json()["error"]["message"]
        # Cümle sayıyı ve yönü söylemeli; "tutarsız" demekle yetinmemeli.
        assert "3 soru ediyor" in mesaj
        assert "5" in mesaj
        assert "Kolay" in mesaj

    async def test_tutarli_dagilim_kaydedilir_ve_toplamlar_turetilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="BP 102")
        outcome = await make_outcome(client, fixture, code="CO1")

        response = await client.post(
            f"/courses/{fixture.course_id}/blueprints",
            json={
                "title": "Vize",
                "duration_minutes": 60,
                "cells": [cell(outcome, count=2, points=10)],
                "targets": {"total_questions": 2, "by_question_type": {"mcq": 2}},
            },
            headers=fixture.instructor,
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["total_questions"] == 2
        assert body["total_points"] == 20
        assert body["cells"][0]["label"] == "CO1 · kolay · çoktan seçmeli"

    async def test_baska_dersin_ciktisi_hucreye_baglanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        birinci = await build(client, users, admin_engine, code="BP 103")
        ikinci = await build(client, users, admin_engine, code="BP 104")
        yabanci = await make_outcome(client, ikinci, code="CO9")

        response = await client.post(
            f"/courses/{birinci.course_id}/blueprints",
            json={
                "title": "Vize",
                "duration_minutes": 60,
                "cells": [cell(yabanci, count=1)],
            },
            headers=birinci.instructor,
        )

        assert response.status_code == 422, response.text
        assert "bu derste yok" in response.json()["error"]["message"]

    async def test_konu_dagilimi_turetilir_ve_konusuz_cikti_gorunur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="BP 105")
        konulu = await make_outcome(client, fixture, code="CO1", topic=True)
        konusuz = await make_outcome(client, fixture, code="CO2", topic=False)

        blueprint_id = await make_blueprint(
            client,
            fixture,
            cells=[
                cell(konulu, count=3),
                cell(konusuz, count=2, difficulty="hard"),
            ],
        )

        response = await client.get(
            f"/courses/{fixture.course_id}/blueprints/{blueprint_id}",
            headers=fixture.instructor,
        )
        dagitim = {
            (row["topic_name"] or "KONUSUZ"): row["question_count"]
            for row in response.json()["topic_distribution"]
        }

        assert dagitim == {"Kilitlenme": 3, "KONUSUZ": 2}


class TestYayinKapisi:
    """FR-114 ve §8 madde 7 — eksik hücre ile sınıflandırılmamış kalem AYRI raporlanır."""

    async def test_eksik_hucre_raporlanir_ve_yayin_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="GATE 101")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=2)])
        version_id = await make_version(client, fixture, blueprint_id)

        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        assert (
            await set_items(client, fixture, blueprint_id, version_id, [soru])
        ).status_code == 200

        rapor = await client.get(
            f"/courses/{fixture.course_id}/blueprints/{blueprint_id}"
            f"/versions/{version_id}/readiness",
            headers=fixture.instructor,
        )
        body = rapor.json()

        assert body["ready"] is False
        assert body["unclassified_items"] == []
        assert len(body["missing_cells"]) == 1
        assert body["missing_cells"][0]["required"] == 2
        assert body["missing_cells"][0]["filled"] == 1
        assert "CO1 · kolay · çoktan seçmeli" in body["missing_cells"][0]["label"]
        assert "eksik" in body["missing_cells"][0]["label"]

        reddedildi = await publish(client, fixture, blueprint_id, version_id)
        assert reddedildi.status_code == 409, reddedildi.text

    async def test_siniflandirilmamis_kalem_eksik_hucreden_AYRI_raporlanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Kararın kendisi budur: tek listede görünseydi öğretmen yanlış hücreyi kovalardı."""
        fixture = await build(client, users, admin_engine, code="GATE 102")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])
        version_id = await make_version(client, fixture, blueprint_id)

        sinifli = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        sinifsiz = await make_question(admin_engine, fixture, outcome_id=None, difficulty=None)
        await set_items(client, fixture, blueprint_id, version_id, [sinifli, sinifsiz])

        body = (
            await client.get(
                f"/courses/{fixture.course_id}/blueprints/{blueprint_id}"
                f"/versions/{version_id}/readiness",
                headers=fixture.instructor,
            )
        ).json()

        # Hücre DOLU: sınıflandırılmamış kalem onu bozmuyor, ayrı bir madde olarak duruyor.
        assert body["missing_cells"] == []
        assert len(body["unclassified_items"]) == 1
        madde = body["unclassified_items"][0]
        assert madde["question_id"] == str(sinifsiz)
        assert set(madde["missing_fields"]) == {"learning_outcome", "difficulty"}
        assert "öğrenme çıktısı ve zorluk seviyesi" in madde["label"]
        assert body["ready"] is False

        reddedildi = await publish(client, fixture, blueprint_id, version_id)
        assert reddedildi.status_code == 409
        assert "sınıflandırılmamış" in reddedildi.json()["error"]["message"]

    async def test_onaysiz_soru_kagida_konulamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-119 — blueprint akışı onay kapısını GEVŞETMEZ."""
        fixture = await build(client, users, admin_engine, code="GATE 103")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])
        version_id = await make_version(client, fixture, blueprint_id)

        taslak = await make_question(
            admin_engine, fixture, outcome_id=outcome, difficulty="easy", status="draft"
        )

        response = await set_items(client, fixture, blueprint_id, version_id, [taslak])

        assert response.status_code == 409, response.text
        assert "Onaylanmamış" in response.json()["error"]["message"]


class TestSurumDegismezligi:
    """FR-115 — yayınlanmış sürüm ve onun dağılım kanıtı donar."""

    async def test_yayin_dagilimi_dondurur_ve_sonraki_duzenleme_kaniti_degistirmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """§8 madde 1'in kararı: hücreler düzenlenebilir kalır, kanıt donar."""
        fixture = await build(client, users, admin_engine, code="VER 101")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(
            client, fixture, cells=[cell(outcome, count=1, points=5)]
        )
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])

        yayin = await publish(client, fixture, blueprint_id, version_id)
        assert yayin.status_code == 200, yayin.text
        donmus = yayin.json()["blueprint_snapshot"]
        assert len(donmus) == 1
        assert donmus[0]["question_count"] == 1
        assert donmus[0]["points_per_question"] == 5
        assert donmus[0]["learning_outcome_code"] == "CO1"

        # Blueprint'in hücresi SONRADAN değişiyor (kilitli değil).
        guncelleme = await client.post(
            f"/courses/{fixture.course_id}/blueprints/{blueprint_id}",
            json={"cells": [cell(outcome, count=7, points=3)]},
            headers=fixture.instructor,
        )
        assert guncelleme.status_code == 200, guncelleme.text
        assert guncelleme.json()["total_questions"] == 7

        # Yayınlanmış sürümün kanıtı DEĞİŞMEDİ.
        async with admin_engine.begin() as conn:
            kayit = (
                await conn.execute(
                    text("SELECT blueprint_snapshot FROM exam_versions WHERE id = :id"),
                    {"id": version_id},
                )
            ).scalar_one()
        assert kayit[0]["question_count"] == 1
        assert kayit[0]["points_per_question"] == 5

    async def test_yayinlanmis_surumun_soru_listesi_degistirilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="VER 102")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])
        assert (await publish(client, fixture, blueprint_id, version_id)).status_code == 200

        baska = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        response = await set_items(client, fixture, blueprint_id, version_id, [baska])

        assert response.status_code == 409, response.text
        assert "yeni bir sürüm" in response.json()["error"]["message"].lower()

    async def test_ikinci_yayin_oncekini_superseded_yapar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="VER 103")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])

        v1 = await make_version(client, fixture, blueprint_id)
        s1 = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, v1, [s1])
        assert (await publish(client, fixture, blueprint_id, v1)).status_code == 200

        v2 = await make_version(client, fixture, blueprint_id)
        s2 = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, v2, [s2])
        assert (await publish(client, fixture, blueprint_id, v2)).status_code == 200

        surumler = (
            await client.get(
                f"/courses/{fixture.course_id}/blueprints/{blueprint_id}/versions",
                headers=fixture.instructor,
            )
        ).json()
        durum = {row["version_no"]: row["status"] for row in surumler}

        assert durum == {1: "superseded", 2: "published"}

    async def test_yuruyen_oturum_BASLADIGI_surumu_gormeye_devam_eder(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """§8 madde 9'un kararı — sınav ortasında kâğıt değişmez."""
        fixture = await build(client, users, admin_engine, code="VER 104")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(
            client, fixture, cells=[cell(outcome, count=1)], max_attempts=3
        )

        v1 = await make_version(client, fixture, blueprint_id)
        s1 = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, v1, [s1])
        await publish(client, fixture, blueprint_id, v1)

        acilis = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"blueprint_id": str(blueprint_id)},
            headers=fixture.student,
        )
        assert acilis.status_code == 201, acilis.text
        oturum = acilis.json()
        assert oturum["exam_version_id"] == str(v1)
        assert oturum["attempt_no"] == 1
        assert [q["id"] for q in oturum["questions"]] == [str(s1)]

        # Öğretmen ikinci sürümü BAŞKA bir soruyla yayınlıyor.
        v2 = await make_version(client, fixture, blueprint_id)
        s2 = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, v2, [s2])
        await publish(client, fixture, blueprint_id, v2)

        devam = await client.get(
            f"/courses/{fixture.course_id}/exams/{oturum['id']}", headers=fixture.student
        )
        govde = devam.json()

        assert govde["exam_version_id"] == str(v1), "yürüyen oturum sürüm değiştirmemeli"
        assert [q["id"] for q in govde["questions"]] == [str(s1)]
        assert govde["question_count"] == 1


class TestYayinPenceresi:
    """FR-116."""

    async def test_yayinlanmamis_sinava_oturum_acilamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="WIN 101")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])

        response = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"blueprint_id": str(blueprint_id)},
            headers=fixture.student,
        )

        # RLS uygulama katmanından ÖNCE cevap veriyor: `exam_blueprints_read`
        # öğrenciye yalnız "yayınlanmış sürümü olan + penceresi açık" blueprint'i
        # gösteriyor, bu yüzden taslak sınav öğrenci için hiç YOK. 404, 409'dan
        # daha doğru: FR-116 "öğrenci sınavı GÖRMEMELİ" diyor ve varlığı sızdırmamak
        # `_load_exam`'in de kurduğu desen. "Henüz yayınlanmadı" cümlesine yalnız
        # eğitmen ulaşabilir; öğrenciye o cümle sınavın varlığını söylerdi.
        assert response.status_code == 404, response.text
        assert response.json()["error"]["message"] == "Sınav bulunamadı."

    async def test_pencere_kapaliyken_yeni_oturum_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="WIN 102")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(client, fixture, cells=[cell(outcome, count=1)])
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])
        await publish(client, fixture, blueprint_id, version_id)

        # Pencereyi geçmişe alıyoruz (istemci saatiyle değil, veritabanı saatiyle).
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE exam_blueprints SET opens_at = now() - interval '2 day', "
                    "closes_at = now() - interval '1 day' WHERE id = :id"
                ),
                {"id": blueprint_id},
            )

        response = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"blueprint_id": str(blueprint_id)},
            headers=fixture.student,
        )

        # Pencere kapanınca `app.blueprint_open_to_students` false döner ve blueprint
        # öğrencinin görüşünden tamamen çıkar — yine 404. Uygulama katmanındaki
        # "süresi doldu" cümlesi ikinci katman olarak duruyor ve eğitmen bağlamında
        # ulaşılabilir; öğrenci için kapı daha erken kapanıyor.
        assert response.status_code == 404, response.text
        assert response.json()["error"]["message"] == "Sınav bulunamadı."

    async def test_blueprint_suresi_global_ayarla_KIRPILMAZ(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-111: süre blueprint'in alanı; global 20 dakika artık yalnız provanın.

        Bu kusur tarayıcıda ölçüldü: 45 dakikalık sınav 1200 saniye kalan süreyle
        açılıyordu, çünkü `effective_expiry` her oturumu global sınırla kırpıyordu.
        Kırpma kuralı kalkmadı — yalnız blueprint oturumunda sınav kendi süresini
        veriyor.
        """
        fixture = await build(client, users, admin_engine, code="WIN 104")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(
            client, fixture, cells=[cell(outcome, count=1)], duration=45
        )
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])
        await publish(client, fixture, blueprint_id, version_id)

        oturum = (
            await client.post(
                f"/courses/{fixture.course_id}/exams",
                json={"blueprint_id": str(blueprint_id)},
                headers=fixture.student,
            )
        ).json()

        # 45 dakika = 2700 sn. Global varsayılan 20 dakika (1200 sn) olsaydı kırpardı.
        assert oturum["remaining_seconds"] > 2000, oturum["remaining_seconds"]
        assert oturum["remaining_seconds"] <= 45 * 60

    async def test_prova_oturumu_global_sinirla_KIRPILMAYA_devam_eder(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Regresyon: kırpma kuralı prova akışında aynen duruyor."""
        fixture = await build(client, users, admin_engine, code="WIN 105")
        outcome = await make_outcome(client, fixture, code="CO1")
        await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")

        oturum = (
            await client.post(
                f"/courses/{fixture.course_id}/exams",
                json={"mode": "exam"},
                headers=fixture.student,
            )
        ).json()

        assert oturum["remaining_seconds"] <= 20 * 60

    async def test_blueprint_suresi_boyunca_asistan_KILITLI_kalir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """US1 kilidi blueprint süresini görmeli, global sınırı değil.

        Bu testi mutasyon koşusu ısmarladı: `active_exam_session` içindeki kırpma
        global sınıra sabitlendiğinde HİÇBİR test kırmızı yanmıyordu. Oysa kusur
        ağır: 45 dakikalık sınavın 21. dakikasında asistan kendiliğinden açılırdı —
        fail-open, yani kilidin tam tersi (Anayasa IV).

        Kurgu: oturum 25 dakika geriye alınır. Blueprint süresi 45 olduğu için
        oturum HÂLÂ yürüyor; global 20 dakikalık sınır uygulansaydı çoktan bitmiş
        sayılırdı.
        """
        fixture = await build(client, users, admin_engine, code="LOCK 101")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(
            client, fixture, cells=[cell(outcome, count=1)], duration=45
        )
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])
        await publish(client, fixture, blueprint_id, version_id)

        oturum = (
            await client.post(
                f"/courses/{fixture.course_id}/exams",
                json={"blueprint_id": str(blueprint_id)},
                headers=fixture.student,
            )
        ).json()

        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE exam_sessions SET started_at = started_at - interval '25 min' "
                    "WHERE id = :id"
                ),
                {"id": oturum["id"]},
            )

        yoklama = await client.get(
            f"/courses/{fixture.course_id}/chat/availability", headers=fixture.student
        )
        assert yoklama.json()["available"] is False, "45 dakikalık sınav sürerken asistan açık"

        sohbet = await client.post(
            f"/courses/{fixture.course_id}/chat",
            json={"message": "Kilitlenme nedir?", "mode": "qa"},
            headers=fixture.student,
        )
        assert sohbet.status_code == 403, sohbet.text
        assert sohbet.json()["error"]["code"] == "exam_in_progress"

    async def test_deneme_hakki_bitince_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build(client, users, admin_engine, code="WIN 103")
        outcome = await make_outcome(client, fixture, code="CO1")
        blueprint_id = await make_blueprint(
            client, fixture, cells=[cell(outcome, count=1)], max_attempts=1
        )
        version_id = await make_version(client, fixture, blueprint_id)
        soru = await make_question(admin_engine, fixture, outcome_id=outcome, difficulty="easy")
        await set_items(client, fixture, blueprint_id, version_id, [soru])
        await publish(client, fixture, blueprint_id, version_id)

        birinci = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"blueprint_id": str(blueprint_id)},
            headers=fixture.student,
        )
        assert birinci.status_code == 201, birinci.text

        ikinci = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"blueprint_id": str(blueprint_id)},
            headers=fixture.student,
        )

        assert ikinci.status_code == 409, ikinci.text
        assert "deneme hakkınız" in ikinci.json()["error"]["message"]


async def _yetki_reddedilmeli(statement: str) -> None:
    """`dou_app` ile verilen yazmayı dener ve yetki hatası bekler.

    Satır bulunmasa bile PostgreSQL yetkiyi ÖNCE kontrol eder, yani boş tabloda da
    anlamlı bir testtir.

    Çağıran testler `client` fixture'ını **kullanmasalar da** isterler: paylaşılan
    motoru kapatan `dispose_engine()` o fixture'ın teardown'ında koşuyor ve
    kapatılmazsa oturum sonundaki DROP DATABASE açık bağlantıya takılır.
    """
    with pytest.raises(ProgrammingError) as hata:
        async with rls_session(user_id=uuid4()) as session:
            await session.execute(text(statement))
    mesaj = str(hata.value).lower()
    assert "izin" in mesaj or "permission" in mesaj, mesaj


class TestYetkiler:
    """`data-model.md` §2.13'ün "sessiz kalabilecek hata"sı: REVOKE satırları.

    Bu testler uygulama kodundan geçmez, doğrudan `dou_app` bağlantısıyla yazmayı
    dener. REVOKE unutulsaydı davranış testlerinin hiçbiri kırmızı yanmazdı, çünkü
    uygulama kodu zaten UPDATE atmıyor.
    """

    async def test_dou_app_exam_items_guncelleyemez(self, client: AsyncClient) -> None:
        await _yetki_reddedilmeli("UPDATE exam_items SET points = 99")

    async def test_dou_app_blueprint_cells_guncelleyemez(self, client: AsyncClient) -> None:
        await _yetki_reddedilmeli("UPDATE blueprint_cells SET question_count = 99")

    async def test_dou_app_surumun_kimligini_yazamaz(self, client: AsyncClient) -> None:
        """Kolon bazlı GRANT: durum yazılabilir, `version_no` yazılamaz."""
        await _yetki_reddedilmeli("UPDATE exam_versions SET version_no = 99")

    async def test_dou_app_exam_sessions_suresini_yazamaz(self, client: AsyncClient) -> None:
        """0007'nin koruması 0008'den sonra da ayakta (regresyon)."""
        await _yetki_reddedilmeli("UPDATE exam_sessions SET expires_at = now()")


class TestRubrikKirilimi:
    """FR-117 — ölçüt kırılımı ve toplamın nereden geldiği.

    Yeni tablo yok: kırılım `answers.feedback` jsonb'sine yazılır (0004:110-112 tam
    bu iş için var). Sınanan şey toplamın MODELDEN OKUNMADIĞI: ağırlıklarla biz
    hesaplıyoruz, yoksa model hem kırılım hem ayrı bir toplam verdiğinde ikisi
    çelişebilir ve öğrenciye gösterilen tablonun toplamı tutmazdı (Anayasa III).
    """

    def _payload(self, agirliklar: list[int]) -> OpenPayload:
        return OpenPayload(
            prompt="Kilitlenmenin dört koşulunu açıkla.",
            answer_key="Karşılıklı dışlama, tut ve bekle, kesintisizlik, dairesel bekleme.",
            key_points=["dört koşul"],
            rubric=[RubricItem(point=f"olcut-{i}", weight=w) for i, w in enumerate(agirliklar)],
        )

    def _verdict(self, puanlar: dict[str, int] | None) -> _LlmVerdict:
        return _LlmVerdict(
            score=99,  # Model kendi toplamını verir; OKUNMAMALI.
            eksik_noktalar=[],
            dayanak_chunk_id=None,
            rubrik=(
                [] if puanlar is None else [{"olcut": k, "puan": v} for k, v in puanlar.items()]
            ),
        )

    def test_toplam_agirliklarla_hesaplanir_modelin_skoru_okunmaz(self) -> None:
        kirilim = _rubric_breakdown(
            self._payload([60, 40]), self._verdict({"olcut-0": 100, "olcut-1": 50})
        )

        assert [row.earned for row in kirilim] == [60, 20]
        assert sum(row.earned for row in kirilim) == 80  # modelin dediği 99 değil

    def test_modelin_atladigi_olcut_SIFIR_puanla_girer(self) -> None:
        """Fail-closed: atlanan ölçütü paydadan düşürmek puanı şişirirdi."""
        kirilim = _rubric_breakdown(self._payload([50, 50]), self._verdict({"olcut-0": 100}))

        assert [row.score for row in kirilim] == [100, 0]
        assert sum(row.earned for row in kirilim) == 50

    def test_model_HIC_kirilim_vermezse_puan_sessizce_sifirlanmaz(self) -> None:
        """İlk yazımda bu dal yoktu ve gerçekten 75 alan cevap 0'a düşüyordu."""
        kirilim = _rubric_breakdown(self._payload([50, 50]), self._verdict(None))

        assert kirilim == [], "kırılım yoksa çağıran modelin kendi skorunu kullanmalı"

    def test_rubriksiz_soru_bugunku_davranisini_surdurur(self) -> None:
        kirilim = _rubric_breakdown(self._payload([]), self._verdict({"x": 100}))

        assert kirilim == []

    def test_agirliklar_100_etmiyorsa_OKUMA_yolunda_normalize_edilir(self) -> None:
        """Kısıt yalnız yeni üretimde zorlanır; havuzdaki eski sorular düşmemeli."""
        normalize = normalized_rubric(
            [RubricItem(point="a", weight=30), RubricItem(point="b", weight=30)]
        )

        assert sum(item.weight for item in normalize) == 100
        assert [item.point for item in normalize] == ["a", "b"]

    def test_uretimde_agirlik_toplami_100_degilse_taslak_havuza_girmez(self) -> None:
        with pytest.raises(PydanticValidationError) as hata:
            _OpenDraft(
                source_chunk_id=uuid4(),
                prompt="Soru metni burada.",
                answer_key="Cevap",
                key_points=["nokta"],
                rubric=[RubricItem(point="a", weight=30), RubricItem(point="b", weight=30)],
            )

        assert "100 etmeli" in str(hata.value)
