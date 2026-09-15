"""Soru havuzu ucu öğrenciye materyalin METNİNİ vermez — yalnız kimliğini.

Bu dosya tek bir sızıntıyı çivilemek için var ve gerekçesi kardeş uçlarla
karşılaştırmadır. `SourceRefOut.snippet` chunk metninden 320 karakterdir ve aynı
nesne üç yerde daha üretilir; üçü de kapılıdır:

* `POST /exams/{id}/hint` — sınav modunda 403, başka sınav yürürken 403 ve
  `hint_limit: 0` iken 403 (`tests/test_exam_hint_policy.py`).
* `GET /courses/{id}/sources/{chunk_id}` — `UnlockedCourseMemberDep`
  (`tests/test_sources_api.py`, `exam_in_progress`).
* Belge chunk önizlemesi — yalnız eğitmen.

`GET /courses/{id}/questions` ise `CourseMemberDep` ile bağlıdır: sınav kilidini
görmez, politikayı okumaz. Snippet oradan da dönseydi öğrenci sınav sırasında
tek istekle kâğıdındaki her sorunun kaynak pasajını okuyabilir, `hint_limit: 0`
diyen eğitmenin kararı da aynı istekle delinirdi. Bu yüzden öğrenci projeksiyonu
`QuestionSourceRefOut`'tur: `chunk_id` + `file_name` + `location`, metin yok.

Kırılabilirlik: `app/api/questions.py`'deki `visible_source` üçlüsü `source`'a
geri çevrilirse aşağıdaki üç test de kırmızı yanar.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.factories import build_course, start


async def test_ogrenci_soru_havuzunda_kaynak_metnini_gormez(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """Öğrencinin gördüğü kaynak referansında `snippet` alanı hiç bulunmaz."""
    pool = await build_course(client, users, admin_engine, approved=1)

    response = await client.get(f"/courses/{pool.course_id}/questions", headers=pool.student)

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "onaylı soru dönmedi; vaka geçersiz"
    for item in items:
        source = item["source"]
        assert source is not None, "kaynağın KİMLİĞİ gizli değil; alan düşmemeli"
        # Alanın boş gelmesi değil, HİÇ gelmemesi bekleniyor: boş string ileride
        # "ama zaten boştu" diye geri doldurulabilir, eksik alan doldurulamaz.
        assert "snippet" not in source
        assert set(source) == {"chunk_id", "file_name", "location"}


async def test_egitmen_soru_havuzunda_kaynak_metnini_gorur(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """Karşı taraf: kısıtlama öğrenciye özgüdür, eğitmen FR-023 için metni görür.

    Bu test olmadan yukarıdaki iddia, alanı herkesten silerek de yeşil yanardı.
    """
    pool = await build_course(client, users, admin_engine, approved=1)

    response = await client.get(f"/courses/{pool.course_id}/questions", headers=pool.instructor)

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "onaylı soru dönmedi; vaka geçersiz"
    assert all(item["source"]["snippet"] for item in items)


async def test_yuruyen_sinav_ve_kapali_ipucu_soru_havuzundan_delinmez(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """İpucu ucunun 403'ü ile soru havuzunun 200'ü aynı bilgiyi vermemeli.

    Aynı istekte iki kapı birden sınanıyor: sınav yürüyor VE eğitmen ipucunu
    kapatmış. `hint` ucu 403 dönerken `questions` ucu 200 döner (havuzu listelemek
    yasak değil), ama döndüğü kayıtta materyalin metni bulunmaz.
    """
    pool = await build_course(client, users, admin_engine, approved=1)
    base = f"/courses/{pool.course_id}"

    policy = await client.put(f"{base}/ai-policy", headers=pool.instructor, json={"hint_limit": 0})
    assert policy.status_code == 200, policy.text
    exam = await start(client, pool, "exam")

    hint = await client.post(
        f"{base}/exams/{exam['id']}/hint",
        headers=pool.student,
        json={"question_id": str(pool.question_ids[0]), "hint_level": 1},
    )
    assert hint.status_code == 403, hint.text

    listed = await client.get(f"{base}/questions", headers=pool.student)
    assert listed.status_code == 200, listed.text
    for item in listed.json()["items"]:
        assert "snippet" not in item["source"]
