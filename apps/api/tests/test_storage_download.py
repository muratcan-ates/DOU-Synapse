"""İmzalı indirme: servis anahtarından önce ders, belge ve sınav sınırları."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.errors import NotFoundError, StorageUnavailableError
from app.modules.ingestion.storage import (
    LocalFileStorage,
    SupabaseStorage,
    get_storage,
    set_storage,
)
from tests.conftest import UserFactory
from tests.factories import create_course, enroll_student

PROJECT = "https://synthetic-storage.invalid"
BUCKET = "course-materials"
TOKEN = "synthetic-short-lived-token"


def _remote(requests: list[httpx.Request]) -> SupabaseStorage:
    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path.startswith(f"/storage/v1/object/sign/{BUCKET}/")
        assert json.loads(request.content) == {"expiresIn": 60}
        assert request.headers["authorization"] == "Bearer synthetic-server-key"
        return httpx.Response(
            200,
            json={"signedURL": request.url.path.removeprefix("/storage/v1") + f"?token={TOKEN}"},
        )

    return SupabaseStorage(
        project_url=PROJECT,
        service_role_key="synthetic-server-key",
        bucket=BUCKET,
        transport=httpx.MockTransport(respond),
    )


async def _document(
    admin_engine: AsyncEngine, course: UUID, owner: UUID, *, key: str | None = None
) -> tuple[UUID, str]:
    document = uuid4()
    path = key if key is not None else f"courses/{course}/{uuid4().hex}.md"
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO documents "
                "(id, course_id, uploaded_by, file_name, file_type, storage_path, "
                "file_hash, byte_size) "
                "VALUES (:id, :course, :owner, :name, '.md', :path, :hash, 10)"
            ),
            {
                "id": document,
                "course": course,
                "owner": owner,
                "name": "Türkçe ders.md",
                "path": path,
                "hash": uuid4().hex,
            },
        )
    return document, path


async def _exam(admin_engine: AsyncEngine, course: UUID, actor: UUID, state: str) -> None:
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO exam_sessions "
                "(course_id, user_id, mode, started_at, expires_at, finished_at, question_ids) "
                "VALUES (:course, :actor, 'exam', now() - interval '1 minute', "
                "CASE WHEN :state = 'expired' THEN now() - interval '1 second' "
                "ELSE now() + interval '10 minutes' END, "
                "CASE WHEN :state = 'finished' THEN now() ELSE NULL END, '{}')"
            ),
            {"course": course, "actor": actor, "state": state},
        )


async def test_member_receives_same_object_signed_url_after_server_membership(
    client: httpx.AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    instructor = await users.create("teacher-storage@example.com")
    student = await users.create("student-storage@example.com")
    course = await create_course(client, users.auth(instructor), "STORAGE-SIGNED")
    await enroll_student(client, users.auth(instructor), course, "student-storage@example.com")
    document, path = await _document(admin_engine, course, instructor)
    requests: list[httpx.Request] = []
    set_storage(_remote(requests))
    result = await client.get(
        f"/courses/{course}/documents/{document}/download", headers=users.auth(student)
    )
    assert result.status_code == 307, result.text
    assert (
        result.headers["location"]
        == f"{PROJECT}/storage/v1/object/sign/{BUCKET}/{path}?token={TOKEN}"
    )
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["referrer-policy"] == "no-referrer"
    assert result.content == b""
    assert len(requests) == 1


@pytest.mark.parametrize("actor_kind", ["outsider", "revoked", "platform_admin", "anonymous"])
async def test_no_membership_never_calls_service_role_signing(
    actor_kind: str, client: httpx.AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    instructor = await users.create("teacher-storage@example.com")
    actor = await users.create("actor-storage@example.com")
    course = await create_course(client, users.auth(instructor), "STORAGE-DENIED")
    document, _ = await _document(admin_engine, course, instructor)
    async with admin_engine.begin() as connection:
        if actor_kind == "revoked":
            await connection.execute(
                text(
                    "INSERT INTO course_memberships (course_id, user_id, role, status) "
                    "VALUES (:course, :actor, 'student', 'revoked')"
                ),
                {"course": course, "actor": actor},
            )
        if actor_kind == "platform_admin":
            await connection.execute(
                text("INSERT INTO platform_admins (user_id) VALUES (:actor)"), {"actor": actor}
            )
    requests: list[httpx.Request] = []
    set_storage(_remote(requests))
    result = await client.get(
        f"/courses/{course}/documents/{document}/download",
        headers={} if actor_kind == "anonymous" else users.auth(actor),
    )
    assert result.status_code == (401 if actor_kind == "anonymous" else 404), result.text
    assert result.json()["error"]["code"] == (
        "unauthenticated" if actor_kind == "anonymous" else "not_found"
    )
    assert requests == []
    assert "location" not in result.headers


async def test_foreign_document_rejected_even_when_actor_teaches_both_courses(
    client: httpx.AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    actor = await users.create("teacher-storage@example.com")
    first = await create_course(client, users.auth(actor), "STORAGE-A")
    second = await create_course(client, users.auth(actor), "STORAGE-B")
    document, _ = await _document(admin_engine, second, actor)
    requests: list[httpx.Request] = []
    set_storage(_remote(requests))
    result = await client.get(
        f"/courses/{first}/documents/{document}/download", headers=users.auth(actor)
    )
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "not_found"
    assert requests == []


@pytest.mark.parametrize(
    "bad_key",
    [
        "courses/{other}/00000000000000000000000000000000.md",
        "courses/{course}/../private.md",
        "courses/{course}/00000000000000000000000000000000.md/extra",
        "courses/{course}/not-a-server-id.md",
        "courses/{course}/00000000000000000000000000000000.exe",
        "courses/{course}/%2e%2e/private.md",
        "https://foreign.invalid/secret.md",
    ],
)
async def test_tampered_storage_path_never_reaches_service_role(
    bad_key: str, client: httpx.AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    actor = await users.create("teacher-storage@example.com")
    course = await create_course(client, users.auth(actor), "STORAGE-PATH")
    document, _ = await _document(
        admin_engine, course, actor, key=bad_key.format(course=course, other=uuid4())
    )
    requests: list[httpx.Request] = []
    set_storage(_remote(requests))
    result = await client.get(
        f"/courses/{course}/documents/{document}/download", headers=users.auth(actor)
    )
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "not_found"
    assert requests == []


@pytest.mark.parametrize(
    "role,state,expected",
    [
        ("student", "active", 403),
        ("student", "expired", 307),
        ("student", "finished", 307),
        ("instructor", "active", 307),
    ],
)
async def test_download_obeys_exam_lock_with_instructor_exemption(
    role: str,
    state: str,
    expected: int,
    client: httpx.AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    teacher = await users.create("teacher-storage@example.com")
    student = await users.create("student-storage@example.com")
    course = await create_course(client, users.auth(teacher), "STORAGE-EXAM")
    await enroll_student(client, users.auth(teacher), course, "student-storage@example.com")
    actor = teacher if role == "instructor" else student
    document, _ = await _document(admin_engine, course, teacher)
    await _exam(admin_engine, course, actor, state)
    requests: list[httpx.Request] = []
    set_storage(_remote(requests))
    result = await client.get(
        f"/courses/{course}/documents/{document}/download", headers=users.auth(actor)
    )
    assert result.status_code == expected, result.text
    if expected == 403:
        assert result.json()["error"]["code"] == "exam_in_progress"
        assert requests == []
    else:
        assert len(requests) == 1


async def test_local_download_returns_attachment_with_no_cache(
    client: httpx.AsyncClient, users: UserFactory, admin_engine: AsyncEngine, tmp_path: Path
) -> None:
    actor = await users.create("teacher-storage@example.com")
    course = await create_course(client, users.auth(actor), "STORAGE-LOCAL")
    document, path = await _document(admin_engine, course, actor)
    storage = LocalFileStorage(tmp_path / "files")
    await storage.save(path, b"synthetic-course-material")
    set_storage(storage)
    result = await client.get(
        f"/courses/{course}/documents/{document}/download", headers=users.auth(actor)
    )
    assert result.status_code == 200, result.text
    assert result.content == b"synthetic-course-material"
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["content-disposition"] == "attachment; filename*=UTF-8''" + quote(
        "Türkçe ders.md", safe=""
    )
    assert "location" not in result.headers


@pytest.mark.parametrize(
    "signed",
    [
        None,
        123,
        "",
        "//foreign.invalid/object/sign/course-materials/key?token=x",
        "https://foreign.invalid/storage/v1/object/sign/course-materials/key?token=x",
        "http://synthetic-storage.invalid/storage/v1/object/sign/course-materials/key?token=x",
        "/object/public/course-materials/key?token=x",
        "/object/sign/other/key?token=x",
        "/object/sign/course-materials/other?token=x",
        "/object/sign/course-materials/key",
        "/object/sign/course-materials/key?token=",
        "/object/sign/course-materials/key?token=x&token=y",
        "/object/sign/course-materials/key?token=x&extra=1",
        "/object/sign/course-materials/key?token=x#fragment",
        "/object/sign/course-materials/key?token=x\n",
    ],
)
async def test_invalid_signed_destination_is_closed(signed: object) -> None:
    storage = SupabaseStorage(
        project_url=PROJECT,
        service_role_key="synthetic-server-key",
        bucket=BUCKET,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"signedURL": signed})
        ),
    )
    with pytest.raises(StorageUnavailableError):
        await storage.signed_download_url("key")


@pytest.mark.parametrize("absolute", [False, True])
async def test_signed_url_preserves_encoded_bucket_and_object(absolute: bool) -> None:
    path = "/object/sign/ders%20materyalleri/courses/abc/hafta%203.pdf?token=x"
    destination = PROJECT + "/storage/v1" + path

    def respond(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.raw_path
            == b"/storage/v1/object/sign/ders%20materyalleri/courses/abc/hafta%203.pdf"
        )
        return httpx.Response(200, json={"signedURL": destination if absolute else path})

    storage = SupabaseStorage(
        project_url=PROJECT,
        service_role_key="synthetic-server-key",
        bucket="ders materyalleri",
        transport=httpx.MockTransport(respond),
    )
    assert await storage.signed_download_url("courses/abc/hafta 3.pdf") == destination


async def test_signing_missing_object_is_not_found() -> None:
    storage = SupabaseStorage(
        project_url=PROJECT,
        service_role_key="synthetic-server-key",
        bucket=BUCKET,
        transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
    )
    with pytest.raises(NotFoundError):
        await storage.signed_download_url("key")


def test_runtime_rejects_unmanaged_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    settings = Settings(
        dev_auth_enabled=True,
        storage_backend="supabase",
        supabase_url=PROJECT,
        supabase_service_role_key="synthetic-server-key",
        supabase_storage_bucket="unmanaged",
    )
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    set_storage(None)
    with pytest.raises(ValueError, match="course-materials"):
        get_storage()


def test_download_openapi_declares_binary_response_and_private_redirect() -> None:
    from app.main import create_app

    schema = create_app().openapi()
    responses = schema["paths"]["/courses/{course_id}/documents/{document_id}/download"]["get"][
        "responses"
    ]
    assert responses["200"]["content"] == {
        "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
    }
    assert responses["200"]["headers"]["Content-Disposition"]["schema"]["type"] == "string"
    assert responses["307"]["headers"]["Location"]["schema"] == {
        "type": "string",
        "format": "uri",
    }
    for code in ("200", "307"):
        assert responses[code]["headers"]["Cache-Control"]["schema"]["enum"] == ["no-store"]
