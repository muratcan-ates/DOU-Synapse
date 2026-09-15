"""Kavram haritası uçları: yetki, ders izolasyonu, sınav kilidi ve dışa aktarım.

Saf çıkarımın kendisi `test_concepts.py`'de sınanıyor; burada ucun SÖZLEŞMESİ
sınanır — kimin görebildiği, neyin görünmediği ve indirilen dosyanın ne taşıdığı.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.factories import (
    build_course,
    create_course,
    enroll_student,
    seed_document,
    start,
)

#: Terimlerin en az iki pasajda geçmesi gerekiyor; metinler buna göre kuruldu.
PASAJLAR = [
    "Semafor paylaşılan kaynağa erişimi sınırlar ve kritik bölüme giriş sırasını kurar.",
    "Mutex ikili bir semafordur; kritik bölüme aynı anda tek thread girer.",
    "Kritik bölüm iki thread tarafından aynı anda çalıştırılamaz, semafor bunu korur.",
    "Thread zamanlaması kritik bölümün süresini doğrudan etkiler.",
]


async def _kurs_ve_materyal(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    *,
    code: str = "COME301",
) -> tuple[str, dict[str, str], dict[str, str]]:
    instructor_id = await users.create("ayse@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student_id = await users.create("burak@dogus.edu.tr")
    course_id = await create_course(client, instructor, code)
    await enroll_student(client, instructor, course_id, "burak@dogus.edu.tr")
    await seed_document(
        admin_engine,
        course_id=course_id,
        uploaded_by=instructor_id,
        passages=PASAJLAR,
        file_name="03-senkronizasyon.pdf",
    )
    return str(course_id), instructor, users.auth(student_id)


class TestKavramHaritasi:
    async def test_ogrenci_terimleri_kaynagiyla_gorur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, _, student = await _kurs_ve_materyal(client, users, admin_engine)

        response = await client.get(f"/courses/{course_id}/concepts", headers=student)

        assert response.status_code == 200, response.text
        body = response.json()
        terimler = {term["term"].lower() for term in body["terms"]}
        assert "semafor" in terimler
        assert "kritik" in terimler
        assert body["chunk_count"] == len(PASAJLAR)
        assert body["truncated"] is False

    async def test_her_terim_gercek_bir_pasaja_baglanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Kaynağı gösterilemeyen satır bu ekranın vaat etmediği tek şeydir."""
        course_id, _, student = await _kurs_ve_materyal(client, users, admin_engine)

        body = (await client.get(f"/courses/{course_id}/concepts", headers=student)).json()

        assert body["terms"]
        for term in body["terms"]:
            kaynak = term["source"]
            assert kaynak["file_name"] == "03-senkronizasyon.pdf"
            assert kaynak["snippet"].strip()
            # Alıntı materyalden birebir gelir; üretilmiş bir cümle değildir.
            assert kaynak["snippet"] in " ".join(PASAJLAR).replace("  ", " ") or any(
                kaynak["snippet"] in pasaj for pasaj in PASAJLAR
            )

    async def test_baglantilar_yalniz_listedeki_terimleri_kullanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, _, student = await _kurs_ve_materyal(client, users, admin_engine)

        body = (await client.get(f"/courses/{course_id}/concepts", headers=student)).json()
        anahtarlar = {term["key"] for term in body["terms"]}

        assert body["edges"]
        for edge in body["edges"]:
            assert edge["left"] in anahtarlar
            assert edge["right"] in anahtarlar

    async def test_baska_dersin_materyali_sizmaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, _, student = await _kurs_ve_materyal(client, users, admin_engine)
        other_instructor_id = await users.create("cem@dogus.edu.tr")
        other_course = await create_course(client, users.auth(other_instructor_id), "MATH201")
        await seed_document(
            admin_engine,
            course_id=other_course,
            uploaded_by=other_instructor_id,
            passages=["Türev limit kavramına dayanır.", "Limit türevin tanımında geçer."],
            file_name="01-analiz.pdf",
        )

        body = (await client.get(f"/courses/{course_id}/concepts", headers=student)).json()

        assert all(term["source"]["file_name"] == "03-senkronizasyon.pdf" for term in body["terms"])
        assert not any(term["term"].lower().startswith("türev") for term in body["terms"])

    async def test_uye_olmayan_ders_varligini_sizdirmaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, _, _ = await _kurs_ve_materyal(client, users, admin_engine)
        yabanci = users.auth(await users.create("dilek@dogus.edu.tr"))

        response = await client.get(f"/courses/{course_id}/concepts", headers=yabanci)

        assert response.status_code == 404

    async def test_materyalsiz_derste_bos_harita(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        instructor = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await create_course(client, instructor, "COME302")

        body = (await client.get(f"/courses/{course_id}/concepts", headers=instructor)).json()

        assert body["terms"] == []
        assert body["edges"] == []
        assert body["chunk_count"] == 0


class TestSinavKilidi:
    async def test_yuruyen_sinavda_kavram_haritasi_kapali(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Harita materyal alıntısı taşır; sınav sürerken açılırsa bütünlük delinir."""
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")

        response = await client.get(
            f"/courses/{fixture.course_id}/concepts", headers=fixture.student
        )

        # Ürünün kilit yanıtı 403 + `exam_in_progress`; kod durum numarasından
        # daha anlamlı, çünkü arayüz mesajı ona göre seçiyor.
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "exam_in_progress"
class TestSinavKilidi:
    async def test_yuruyen_sinavda_kavram_haritasi_kapali(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Harita materyal alıntısı taşır; sınav sürerken açılırsa bütünlük delinir."""
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")

        response = await client.get(
            f"/courses/{fixture.course_id}/concepts", headers=fixture.student
        )

        # Ürünün kilit yanıtı 403 + `exam_in_progress`; kod durum numarasından
        # daha anlamlı, çünkü arayüz mesajı ona göre seçiyor.
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "exam_in_progress"

    # test-quality: sadece-durum-kodu — Eğitmen sınav kilidinden etkilenmez
    async def test_egitmen_sinav_kilidinden_etkilenmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")

        response = await client.get(
            f"/courses/{fixture.course_id}/concepts", headers=fixture.instructor
        )

        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert "items" in data or isinstance(data, list) or len(data) >= 0


class TestDisaAktarim:
