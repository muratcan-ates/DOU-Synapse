"""Ürün portalı, profil ve platform yönetimi güvenlik testleri."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db import rls_session
from app.modules.assessment import exam_state
from tests.conftest import UserFactory


async def _create_course(
    client: AsyncClient,
    headers: dict[str, str],
    code: str,
) -> UUID:
    response = await client.post(
        "/courses",
        json={"code": code, "title": f"{code} Dersi"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def _add_student(
    client: AsyncClient,
    instructor: dict[str, str],
    course_id: UUID,
    email: str,
) -> None:
    response = await client.post(
        f"/courses/{course_id}/members",
        json={"email": email, "role": "student"},
        headers=instructor,
    )
    assert response.status_code == 201, response.text


async def _grant_admin(engine: AsyncEngine, user_id: UUID) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO platform_admins (user_id) VALUES (:user_id)"),
            {"user_id": user_id},
        )


async def _add_exam_session(
    engine: AsyncEngine,
    *,
    course_id: UUID,
    user_id: UUID,
    started_minutes_ago: int,
    expires_minutes_from_now: int,
) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO exam_sessions "
                "(course_id, user_id, mode, started_at, expires_at, question_ids) "
                "VALUES (:course_id, :user_id, 'exam', "
                "now() - (:started_minutes_ago * interval '1 minute'), "
                "now() + (:expires_minutes_from_now * interval '1 minute'), "
                "'{}'::uuid[])"
            ),
            {
                "course_id": course_id,
                "user_id": user_id,
                "started_minutes_ago": started_minutes_ago,
                "expires_minutes_from_now": expires_minutes_from_now,
            },
        )


class TestProfile:
    async def test_profil_uyelikleri_ders_bazli_rolleri_korur(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        owner = await users.create("owner@dogus.edu.tr", "Ders Sahibi")
        mixed = await users.create("mixed@dogus.edu.tr", "Karma Kullanıcı")
        owner_headers = users.auth(owner)
        mixed_headers = users.auth(mixed)

        student_course = await _create_course(client, owner_headers, "COME301")
        await _add_student(client, owner_headers, student_course, "mixed@dogus.edu.tr")
        instructor_course = await _create_course(client, mixed_headers, "COME302")

        response = await client.get("/me/profile", headers=mixed_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["is_platform_admin"] is False
        assert {(item["course_id"], item["role"]) for item in body["memberships"]} == {
            (str(student_course), "student"),
            (str(instructor_course), "instructor"),
        }

    async def test_profil_yalniz_adi_degistirir(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        user_id = await users.create("ayse@dogus.edu.tr", "Eski Ad")
        headers = users.auth(user_id)

        updated = await client.patch(
            "/me/profile",
            json={"full_name": "  Ayşe   Karagül  "},
            headers=headers,
        )
        rejected = await client.patch(
            "/me/profile",
            json={"full_name": "Yeni Ad", "email": "baska@dogus.edu.tr"},
            headers=headers,
        )

        assert updated.status_code == 200
        assert updated.json()["full_name"] == "Ayşe Karagül"
        assert updated.json()["email"] == "ayse@dogus.edu.tr"
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "validation_error"

    @pytest.mark.parametrize(
        "forbidden_field, forbidden_value",
        [
            ("role", "instructor"),
            ("is_platform_admin", True),
        ],
    )
    async def test_profil_kullaniciya_kendi_yetkisini_yukseltme_yuzeyi_vermez(
        self,
        forbidden_field: str,
        forbidden_value: object,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        user_id = await users.create("ogrenci@dogus.edu.tr", "Öğrenci")
        headers = users.auth(user_id)

        response = await client.patch(
            "/me/profile",
            json={"full_name": "Yeni Ad", forbidden_field: forbidden_value},
            headers=headers,
        )
        unchanged = await client.get("/me/profile", headers=headers)

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert unchanged.status_code == 200
        assert unchanged.json()["full_name"] == "Öğrenci"
        assert unchanged.json()["is_platform_admin"] is False

    async def test_profil_adi_null_olamaz(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        headers = users.auth(await users.create("ayse@dogus.edu.tr", "Ayşe"))

        response = await client.patch(
            "/me/profile",
            json={"full_name": None},
            headers=headers,
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    async def test_bos_ad_reddedilir(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        headers = users.auth(await users.create("ayse@dogus.edu.tr"))
        response = await client.patch(
            "/me/profile",
            json={"full_name": "   "},
            headers=headers,
        )
        assert response.status_code == 422


class TestDashboard:
    async def test_karma_rol_tek_global_role_diye_duzlestirilmez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        owner = await users.create("owner@dogus.edu.tr")
        mixed = await users.create("mixed@dogus.edu.tr", "Karma Kullanıcı")
        owner_headers = users.auth(owner)
        mixed_headers = users.auth(mixed)

        student_course = await _create_course(client, owner_headers, "COME311")
        await _add_student(client, owner_headers, student_course, "mixed@dogus.edu.tr")
        instructor_course = await _create_course(client, mixed_headers, "COME312")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO documents "
                    "(course_id, uploaded_by, file_name, file_type, storage_path, file_hash, "
                    "byte_size, status, error_message) VALUES "
                    "(:course_id, :owner_id, 'gizli-hatali-kaynak.pdf', 'pdf', "
                    "'/private/failed.pdf', 'dashboard-failed-doc', 10, 'failed', "
                    "'öğrenciye görünmemeli')"
                ),
                {"course_id": student_course, "owner_id": owner},
            )
            await connection.execute(
                text(
                    "INSERT INTO documents "
                    "(course_id, uploaded_by, file_name, file_type, storage_path, file_hash, "
                    "byte_size, status, error_message) VALUES "
                    "(:course_id, :owner_id, 'gizli-egitmen-kaynagi.pdf', 'pdf', "
                    "'/private/instructor.pdf', 'dashboard-instructor-failed-doc', 10, "
                    "'failed', 'öğretmen gizli hata')"
                ),
                {"course_id": instructor_course, "owner_id": mixed},
            )

        response = await client.get("/dashboard", headers=mixed_headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["summary"] == {
            "total_courses": 2,
            "instructor_courses": 1,
            "student_courses": 1,
            "action_items": 1,
        }
        roles = {item["id"]: item["role"] for item in body["courses"]}
        assert roles[str(student_course)] == "student"
        assert roles[str(instructor_course)] == "instructor"
        student_card = next(item for item in body["courses"] if item["id"] == str(student_course))
        instructor_card = next(
            item for item in body["courses"] if item["id"] == str(instructor_course)
        )
        assert student_card["documents_failed"] == 0
        assert student_card["draft_questions"] == 0
        assert instructor_card["documents_failed"] == 1
        assert "gizli-egitmen-kaynagi.pdf" not in response.text
        assert "/private/instructor.pdf" not in response.text
        assert "öğretmen gizli hata" not in response.text

    async def test_ogrenci_kilidi_ayni_sure_kuraliyla_ders_bazli_doner(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        owner = await users.create("owner@dogus.edu.tr")
        mixed = await users.create("mixed@dogus.edu.tr")
        owner_headers = users.auth(owner)
        mixed_headers = users.auth(mixed)

        locked_course = await _create_course(client, owner_headers, "LOCK311")
        capped_course = await _create_course(client, owner_headers, "CAP312")
        await _add_student(client, owner_headers, locked_course, "mixed@dogus.edu.tr")
        await _add_student(client, owner_headers, capped_course, "mixed@dogus.edu.tr")
        instructor_course = await _create_course(client, mixed_headers, "TEACH313")

        duration = get_settings().exam_duration_minutes
        await _add_exam_session(
            admin_engine,
            course_id=locked_course,
            user_id=mixed,
            started_minutes_ago=1,
            expires_minutes_from_now=duration + 10,
        )
        # expires_at gelecekte kalsa da etkin süre started_at + global sınırda
        # biter. Dashboard yalnız expires_at'e bakarsa bu ders yanlış kilitlenir.
        await _add_exam_session(
            admin_engine,
            course_id=capped_course,
            user_id=mixed,
            started_minutes_ago=duration + 1,
            expires_minutes_from_now=duration + 10,
        )
        # Eğitmen kendi dersinde sınav satırı taşısa bile dashboard kilidi yalnız
        # öğrenci üyelikleri için değerlendirmelidir.
        await _add_exam_session(
            admin_engine,
            course_id=instructor_course,
            user_id=mixed,
            started_minutes_ago=1,
            expires_minutes_from_now=duration + 10,
        )

        response = await client.get("/dashboard", headers=mixed_headers)

        assert response.status_code == 200, response.text
        cards = {UUID(item["id"]): item for item in response.json()["courses"]}
        assert cards[locked_course]["assistant_locked"] is True
        assert cards[locked_course]["assistant_lock_reason"] == exam_state.EXAM_LOCK_REASON
        assert cards[locked_course]["assistant_lock_message"] == exam_state.EXAM_LOCK_MESSAGE
        assert cards[capped_course]["assistant_locked"] is False
        assert cards[capped_course]["assistant_lock_reason"] is None
        assert cards[capped_course]["assistant_lock_message"] is None
        assert cards[instructor_course]["role"] == "instructor"
        assert cards[instructor_course]["assistant_locked"] is False
        assert cards[instructor_course]["assistant_lock_reason"] is None
        assert cards[instructor_course]["assistant_lock_message"] is None

    async def test_ogrenci_dersleri_kilit_yardimcisina_tek_partide_verilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        owner = await users.create("owner@dogus.edu.tr")
        mixed = await users.create("mixed@dogus.edu.tr")
        owner_headers = users.auth(owner)
        mixed_headers = users.auth(mixed)
        first_student_course = await _create_course(client, owner_headers, "BATCH311")
        second_student_course = await _create_course(client, owner_headers, "BATCH312")
        await _add_student(
            client,
            owner_headers,
            first_student_course,
            "mixed@dogus.edu.tr",
        )
        await _add_student(
            client,
            owner_headers,
            second_student_course,
            "mixed@dogus.edu.tr",
        )
        instructor_course = await _create_course(client, mixed_headers, "BATCH313")
        calls: list[tuple[UUID, set[UUID]]] = []

        async def _batched(*_args: object, **kwargs: object) -> dict[UUID, object]:
            user_id = kwargs["user_id"]
            course_ids = kwargs["course_ids"]
            assert isinstance(user_id, UUID)
            assert isinstance(course_ids, set)
            calls.append((user_id, course_ids))
            return {first_student_course: object()}

        monkeypatch.setattr(exam_state, "active_exam_sessions_by_course", _batched)

        response = await client.get("/dashboard", headers=mixed_headers)

        assert response.status_code == 200, response.text
        assert calls == [(mixed, {first_student_course, second_student_course})]
        cards = {UUID(item["id"]): item for item in response.json()["courses"]}
        assert cards[first_student_course]["assistant_locked"] is True
        assert cards[second_student_course]["assistant_locked"] is False
        assert cards[instructor_course]["assistant_locked"] is False

    async def test_dersi_olmayan_kullanici_bos_panel_gorur(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        headers = users.auth(await users.create("yeni@dogus.edu.tr"))
        response = await client.get("/dashboard", headers=headers)
        assert response.status_code == 200
        assert response.json()["courses"] == []
        assert response.json()["summary"]["total_courses"] == 0


class TestPlatformAdmin:
    async def test_normal_kullanici_admin_uclarindan_403_alir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        user_id = await users.create("normal@dogus.edu.tr")
        headers = users.auth(user_id)
        expected_actions = {
            "GET /admin/overview",
            "POST /admin/users",
            "GET /admin/courses",
            "GET /admin/requests",
            "GET /admin/ingestion",
        }
        for method, path in (
            ("GET", "/admin/overview"),
            ("POST", "/admin/users"),
            ("GET", "/admin/courses"),
            ("GET", "/admin/requests"),
            ("GET", "/admin/ingestion"),
        ):
            response = await client.request(method, path, headers=headers, json={})
            assert response.status_code == 403, (path, response.text)
            assert response.json()["error"]["code"] == "permission_denied"

        async with admin_engine.connect() as connection:
            audit_rows = (
                await connection.execute(
                    text(
                        "SELECT actor_user_id, action, result, request_id "
                        "FROM platform_admin_access_audit ORDER BY created_at, id"
                    )
                )
            ).all()
        assert len(audit_rows) == 5
        assert {row.action for row in audit_rows} == expected_actions
        assert all(row.actor_user_id == user_id for row in audit_rows)
        assert all(row.result == "denied" for row in audit_rows)
        assert all(row.request_id for row in audit_rows)

    async def test_admin_guvenli_ozet_ve_maskeli_kullanici_listesi_gorur(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        admin_id = await users.create("admin@dogus.edu.tr", "Platform Yöneticisi")
        await users.create("ogrenci@dogus.edu.tr", "Öğrenci")
        await _grant_admin(admin_engine, admin_id)
        headers = users.auth(admin_id)
        course_id = await _create_course(client, headers, "COME410")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO request_logs "
                    "(course_id, user_id, route, mode, status, http_status, "
                    "latency_ms, token_count, cache_hit) VALUES "
                    "(:course_id, :user_id, 'POST /courses/{course_id}/chat', "
                    "'qa', 'answered', 200, 10, 11, false), "
                    "(:course_id, :user_id, 'POST /courses/{course_id}/chat', "
                    "'qa', NULL, 500, 20, NULL, false), "
                    "(:course_id, :user_id, 'GET /health/ready', "
                    "'qa', 'answered', 200, 30, 99, false)"
                ),
                {"course_id": course_id, "user_id": admin_id},
            )

        unsafe_request_id = "ogrenci@dogus.edu.tr/private"
        overview = await client.get(
            "/admin/overview",
            headers={**headers, "X-Request-ID": unsafe_request_id},
        )
        listed = await client.post("/admin/users", headers=headers, json={})

        assert overview.status_code == 200, overview.text
        assert overview.json()["status"] == "ok"
        assert overview.json()["database_status"] == "ok"
        assert overview.json()["active_memberships_total"] == 1
        assert overview.json()["chat_turns_24h"] == 1
        assert overview.json()["tokens_24h"] == 11
        assert "requests_24h" not in overview.json()
        assert "failed_requests_24h" not in overview.json()
        assert overview.json()["embedding_status"] in {
            "disabled",
            "warming",
            "ok",
            "failed",
        }
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 2
        for item in listed.json()["items"]:
            assert "email" not in item
            assert "masked_email" in item
            assert item["masked_email"] not in {
                "admin@dogus.edu.tr",
                "ogrenci@dogus.edu.tr",
            }
        async with admin_engine.connect() as connection:
            audit_rows = (
                await connection.execute(
                    text(
                        "SELECT actor_user_id, action, result, request_id "
                        "FROM platform_admin_access_audit ORDER BY created_at, id"
                    )
                )
            ).all()
        assert {row.action for row in audit_rows} == {
            "GET /admin/overview",
            "POST /admin/users",
        }
        assert all(row.actor_user_id == admin_id for row in audit_rows)
        assert all(row.result == "allowed" for row in audit_rows)
        overview_audit = next(row for row in audit_rows if row.action == "GET /admin/overview")
        assert overview_audit.request_id == overview.headers["X-Request-ID"]
        assert overview_audit.request_id != unsafe_request_id

    async def test_admin_sayfalama_sinirlari_api_tarafindan_zorlanir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        admin_id = await users.create("admin@dogus.edu.tr")
        await _grant_admin(admin_engine, admin_id)
        headers = users.auth(admin_id)
        for payload in ({"limit": 101}, {"offset": -1}, {"offset": None}):
            response = await client.post(
                "/admin/users",
                headers=headers,
                json=payload,
            )
            assert response.status_code == 422, (payload, response.text)

        for path in ("/admin/courses", "/admin/requests", "/admin/ingestion"):
            response = await client.get(f"{path}?offset=-1", headers=headers)
            assert response.status_code == 422, (path, response.text)

    async def test_admin_sql_yardimcilari_sayfalama_bosluklarini_reddeder(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        del client
        admin_id = await users.create("admin@dogus.edu.tr")
        await _grant_admin(admin_engine, admin_id)
        calls = (
            "app.admin_users(CAST(:limit AS integer), CAST(:offset AS integer), NULL)",
            "app.admin_courses(CAST(:limit AS integer), CAST(:offset AS integer), NULL)",
            "app.admin_request_logs(CAST(:limit AS integer), CAST(:offset AS integer), NULL, NULL)",
            "app.admin_ingestion_jobs(CAST(:limit AS integer), CAST(:offset AS integer), NULL)",
        )
        invalid_pages = ((None, 0), (25, None), (25, -1), (0, 0), (101, 0))

        for call in calls:
            for limit, offset in invalid_pages:
                with pytest.raises(DBAPIError):
                    async with rls_session(admin_id) as session:
                        await session.scalar(
                            text(f"SELECT {call}"),
                            {"limit": limit, "offset": offset},
                        )

    @pytest.mark.parametrize("embedding_state", ["warming", "failed"])
    async def test_admin_ozeti_hazir_olmayan_embeddingi_degraded_gosterir(
        self,
        embedding_state: str,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin_id = await users.create("admin@dogus.edu.tr")
        await _grant_admin(admin_engine, admin_id)
        monkeypatch.setattr("app.api.admin.warmup_state", lambda: embedding_state)

        response = await client.get("/admin/overview", headers=users.auth(admin_id))

        assert response.status_code == 200
        assert response.json()["embedding_status"] == embedding_state
        assert response.json()["status"] == "degraded"

    async def test_admin_arama_tam_epostayi_url_parametresine_almaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        admin_id = await users.create("admin@dogus.edu.tr", "Platform Yöneticisi")
        await users.create("ogrenci@dogus.edu.tr", "Öğrenci Kullanıcı")
        await _grant_admin(admin_engine, admin_id)
        headers = users.auth(admin_id)

        by_mask = await client.post(
            "/admin/users",
            headers=headers,
            json={"search": "og***@dogus.edu.tr"},
        )
        by_email = await client.post(
            "/admin/users",
            headers=headers,
            json={"search": "ogrenci@dogus.edu.tr"},
        )

        assert by_mask.status_code == 200
        assert by_mask.json()["total"] == 1
        assert by_email.status_code == 200
        assert by_email.json()["total"] == 0
        assert by_mask.request.url.query == b""
        assert by_email.request.url.query == b""
        assert "ogrenci@dogus.edu.tr" not in str(by_email.request.url)

    async def test_admin_olmak_ders_ve_sohbet_icerigi_yetkisi_vermez(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        owner_id = await users.create("owner@dogus.edu.tr")
        admin_id = await users.create("admin@dogus.edu.tr")
        course_id = await _create_course(client, users.auth(owner_id), "COME401")
        await _grant_admin(admin_engine, admin_id)

        session_id = uuid4()
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO chat_sessions (id, course_id, user_id, mode) "
                    "VALUES (:id, :course_id, :user_id, 'qa')"
                ),
                {"id": session_id, "course_id": course_id, "user_id": owner_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO chat_messages "
                    "(session_id, course_id, role, content, status) "
                    "VALUES (:session_id, :course_id, 'assistant', "
                    "'gizli akademik cevap', 'answered')"
                ),
                {"session_id": session_id, "course_id": course_id},
            )

        course_response = await client.get(
            f"/courses/{course_id}",
            headers=users.auth(admin_id),
        )
        async with rls_session(admin_id) as session:
            visible_messages = await session.scalar(text("SELECT count(*) FROM chat_messages"))

        assert course_response.status_code == 404
        assert visible_messages == 0

    async def test_uygulama_rolu_admin_atayamaz_ve_sql_fonksiyonu_yetkiyi_yeniden_sorar(
        self,
        client: AsyncClient,
        users: UserFactory,
    ) -> None:
        del client  # fixture teardown'u doğrudan rls_session motorunu da kapatır
        user_id = await users.create("normal@dogus.edu.tr")

        with pytest.raises(DBAPIError):
            async with rls_session(user_id) as session:
                await session.execute(
                    text("INSERT INTO platform_admins (user_id) VALUES (:user_id)"),
                    {"user_id": user_id},
                )

        with pytest.raises(DBAPIError):
            async with rls_session(user_id) as session:
                await session.scalar(text("SELECT app.admin_overview()"))

        with pytest.raises(DBAPIError):
            async with rls_session(user_id) as session:
                await session.scalar(text("SELECT count(*) FROM platform_admin_access_audit"))

        with pytest.raises(DBAPIError):
            async with rls_session(user_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO platform_admin_access_audit "
                        "(actor_user_id, action, result, request_id) VALUES "
                        "(:user_id, 'GET /admin/overview', 'allowed', 'sahte')"
                    ),
                    {"user_id": user_id},
                )

    async def test_request_listesi_serbest_metin_ve_kimlik_sizdirmaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        admin_id = await users.create("admin@dogus.edu.tr")
        student_id = await users.create("student@dogus.edu.tr")
        course_id = await _create_course(client, users.auth(student_id), "COME402")
        await _grant_admin(admin_engine, admin_id)
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO request_logs "
                    "(course_id, user_id, route, mode, status, http_status, "
                    "latency_ms, token_count, cache_hit) VALUES "
                    "(:course_id, :user_id, '/courses/x/chat', 'qa', 'answered', "
                    "200, 42, 15, false)"
                ),
                {"course_id": course_id, "user_id": student_id},
            )

        response = await client.get("/admin/requests", headers=users.auth(admin_id))

        assert response.status_code == 200, response.text
        item = response.json()["items"][0]
        assert set(item) == {
            "log_id",
            "course_id",
            "course_code",
            "route",
            "mode",
            "status",
            "http_status",
            "latency_ms",
            "token_count",
            "cache_hit",
            "created_at",
        }
        assert "user_ref" not in item
        assert str(student_id) not in response.text
        assert "student@dogus.edu.tr" not in response.text
        assert "prompt" not in item
        assert "answer" not in item

    async def test_ingestion_listesi_dosya_adi_ve_hata_metni_sizdirmaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        owner_id = await users.create("owner@dogus.edu.tr")
        admin_id = await users.create("admin@dogus.edu.tr")
        course_id = await _create_course(client, users.auth(owner_id), "COME403")
        await _grant_admin(admin_engine, admin_id)
        document_id = uuid4()
        job_id = uuid4()
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO documents "
                    "(id, course_id, uploaded_by, file_name, file_type, storage_path, "
                    "file_hash, byte_size, status, error_message) VALUES "
                    "(:id, :course_id, :owner_id, 'sinav-cevap-anahtari.pdf', 'pdf', "
                    "'/private/secret.pdf', 'portal-secret-hash', 10, 'failed', "
                    "'gizli ayrıştırma hatası')"
                ),
                {"id": document_id, "course_id": course_id, "owner_id": owner_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO ingestion_jobs "
                    "(id, document_id, status, attempt_count, last_error) VALUES "
                    "(:id, :document_id, 'failed', 2, 'gizli worker hatası')"
                ),
                {"id": job_id, "document_id": document_id},
            )

        response = await client.get("/admin/ingestion", headers=users.auth(admin_id))

        assert response.status_code == 200, response.text
        item = response.json()["items"][0]
        assert set(item) == {
            "id",
            "document_id",
            "course_id",
            "course_code",
            "status",
            "attempt_count",
            "started_at",
            "completed_at",
            "created_at",
        }
        assert item["id"] == str(job_id)
        assert "sinav-cevap-anahtari.pdf" not in response.text
        assert "gizli worker hatası" not in response.text
