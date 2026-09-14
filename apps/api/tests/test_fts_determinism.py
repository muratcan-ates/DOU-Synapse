"""Aynı materyal ikinci kez yüklendiğinde FTS sırasının değişmediğini kanıtlar.

## Neden ayrı bir dosya

`test_fts.py` sorgu AYRIŞTIRMA kararlarını (websearch/gevşetme/açık işaret)
sabitliyor. Buradaki iddia başka bir katmanda: sorgu aynı, korpus aynı, değişen
tek şey satırların KİMLİĞİ. Aynı dosyada dursaydı, iki farklı sebeple kırılan
testler tek bir modülün kırmızısına karışırdı.

## Ölçülen kusur

`chunks.id` ve `documents.id` `gen_random_uuid()` ile üretilir. Aynı ders notu
ikinci kez yüklendiğinde parça metni, sayfası ve sırası aynıdır ama kimlikleri
tamamen başkadır. Eşitlik bozma bu kimliklere bakıyorsa, eşit `ts_rank`'li
parçaların sırası korpus yeniden kurulduğunda değişir. R2 bunu ölçtü ve bir
hükmü geri çekmek zorunda kaldı (bkz. `e2d798f` commit gövdesi): yeniden
kurulan indekste Recall@5 0.981 → 0.971 oynadı. `c.id` o turda `c.document_id`
ile değiştirildi, ama `documents.id` de üretilen bir UUID'dir — kusur yer
değiştirdi, kapanmadı.

## Kurgunun dürüstlüğü

Aynı commit gövdesi davranışsal bir kanıt denemesinin "altıda bir şansla"
yeşil kaldığını yazıyor: rastgele UUID'lerle yeniden yükleme, sıranın değişmesi
için yeterli olmayabilir. Buradaki kurgu şansa bırakmaz — iki yüklemenin belge
UUID'leri AÇIKÇA seçilir ve ikisinin sıralaması birbirinin tersidir. Bu, üretimde
`gen_random_uuid()`'nin yarı olasılıkla ürettiği durumun ta kendisidir; test onu
kurmak yerine seçer, böylece kusur varken deterministik olarak kırmızı yanar.

`_ingest_same_material` belgeleri `tests.factories.seed_document` ile değil
yerinde yazar. Sebep, kolaylık değil sadakat: `seed_document` `file_hash` alanına
belge UUID'sinin hex'ini koyuyor, yani orada içerik özeti de kimlikten türüyor ve
bu testin ayırt etmek istediği iki şey (içerik / kimlik) tek değere çöküyor.
Üretimde `file_hash` dosya içeriğinin SHA256'sıdır (`ingestion/pipeline.py`),
aynı dosya yeniden yüklendiğinde aynı kalır. Yardımcı bu davranışı taklit eder.
`seed_document`'ın kendi düzeltmesi ayrı bir iştir (sahibi bu şerit değil).
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.db import rls_session
from app.modules.retrieval.fts import fts_search
from tests.conftest import WORKER_DSN, UserFactory
from tests.factories import create_course


@pytest.fixture
async def worker_engine(clean_tables: None) -> AsyncIterator[AsyncEngine]:
    """Chunk yazımı üretimdeki gibi RLS'i atlayan `dou_worker` rolüyle yapılır."""
    engine = create_async_engine(WORKER_DSN)
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Materyal
#
# İki ayrı ders notu AYNI cümleyi taşıyor. Gerçekçi (özet slaytı dersin cümlesini
# tekrarlar) ve testin ihtiyacı olan şeyi üretiyor: `ts_rank` eşit çıkar, sıra
# eşitlik bozmaya düşer. Cümle aynı, DOSYALAR farklı — `documents` üzerindeki
# `(course_id, file_hash)` UNIQUE kısıtı aynı özetli iki belgeyi zaten kabul
# etmezdi.
# ---------------------------------------------------------------------------

SHARED_SENTENCE = "Semafor kritik bolgeyi korur."

MATERIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("04-senkronizasyon.pdf", (SHARED_SENTENCE, SHARED_SENTENCE)),
    ("09-tekrar-ozeti.pdf", (SHARED_SENTENCE, SHARED_SENTENCE)),
)

#: Birinci yüklemenin belge kimlikleri: birinci dosya < ikinci dosya.
FIRST_INGEST_IDS = (
    UUID("aaaaaaaa-0000-4000-8000-000000000001"),
    UUID("aaaaaaaa-0000-4000-8000-000000000002"),
)
#: İkinci yüklemenin belge kimlikleri: sıralama TERSİNE döndü. `gen_random_uuid()`
#: bunu yaklaşık yarı olasılıkla üretir; test o yarıyı seçer.
SECOND_INGEST_IDS = (
    UUID("bbbbbbbb-0000-4000-8000-000000000002"),
    UUID("bbbbbbbb-0000-4000-8000-000000000001"),
)

_DOCUMENT_SQL = text(
    "INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type, "
    "storage_path, file_hash, byte_size, status, page_count, chunk_count) "
    "VALUES (:id, :course_id, :uploaded_by, :file_name, 'pdf', :path, :hash, "
    "4096, 'completed', :pages, :chunks)"
)

_CHUNK_SQL = text(
    "INSERT INTO chunks (id, course_id, document_id, chunk_index, page_number, "
    "section_title, content_type, text, token_count, embedding_space) "
    "VALUES (:id, :course_id, :document_id, :chunk_index, :page_number, "
    "NULL, 'text', :text, :token_count, NULL)"
)

#: Dönen her parçanın İÇERİKTEN türeyen adresi. `chunk_id` iki yüklemede zaten
#: farklıdır; karşılaştırma ancak kimlikten bağımsız bir adres üzerinden anlamlı.
_ADDRESS_SQL = text(
    "SELECT c.id, d.file_hash, c.chunk_index FROM chunks c "
    "JOIN documents d ON d.id = c.document_id WHERE c.course_id = :course_id"
)


def content_hash(file_name: str, passages: Sequence[str]) -> str:
    """Dosyanın içerik özeti — aynı dosya için her yüklemede aynı değer.

    Üretimdeki `file_hash` dosya baytlarının SHA256'sıdır; burada bayt yok, aynı
    belirleyicilikte bir karşılığı üretiliyor. Dosya adının özete girmesi
    bilinçli: iki ders notu aynı cümleyi taşısa da ayrı dosyalardır ve ayrı
    özetleri olmalıdır.
    """
    payload = "\0".join((file_name, *passages)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def ingest_same_material(
    engine: AsyncEngine,
    *,
    course_id: UUID,
    uploaded_by: UUID,
    document_ids: Sequence[UUID],
) -> None:
    """`MATERIAL`'i verilen belge kimlikleriyle yükler.

    Parça kimlikleri her çağrıda yeniden üretilir (belge kimliğinden türetilir ve
    çağrılar arasında çakışmaz): yeniden yüklemede parça UUID'si de değişir,
    kurgunun taklit ettiği şey budur.
    """
    async with engine.begin() as conn:
        for document_id, (file_name, passages) in zip(document_ids, MATERIAL, strict=True):
            await conn.execute(
                _DOCUMENT_SQL,
                {
                    "id": document_id,
                    "course_id": course_id,
                    "uploaded_by": uploaded_by,
                    "file_name": file_name,
                    "path": f"courses/{course_id}/{document_id.hex}.pdf",
                    "hash": content_hash(file_name, passages),
                    "pages": len(passages),
                    "chunks": len(passages),
                },
            )
            await conn.execute(
                _CHUNK_SQL,
                [
                    {
                        # Parça kimliği belge kimliğinin ÜST bitlerine indeks yazar; alt bitlere
                        # eklemek iki belgenin parçalarını çakıştırıyordu (doc1+2 == doc2+1).
                        "id": UUID(int=(document_id.int ^ ((index + 1) << 96)) % (1 << 128)),
                        "course_id": course_id,
                        "document_id": document_id,
                        "chunk_index": index,
                        "page_number": index + 1,
                        "text": body,
                        "token_count": max(1, len(body.split())),
                    }
                    for index, body in enumerate(passages)
                ],
            )


async def search_addresses(user_id: UUID, course_id: UUID, *, limit: int) -> list[tuple[str, int]]:
    """`fts_search` sonucunu içerikten türeyen adres dizisine çevirir.

    `fts_search` gerçekten çağrılıyor — sorgu SQL'i burada tekrarlanmıyor. Aynı
    kusuru kovalayan ilk iki deneme SQL'in kopyasını sınadığı için kod bozukken
    de yeşil kalmıştı (`e2d798f` commit gövdesi).
    """
    async with rls_session(user_id) as session:
        chunks = await fts_search(session, course_id=course_id, query="semafor", limit=limit)
        address = {
            row.id: (row.file_hash, row.chunk_index)
            for row in (await session.execute(_ADDRESS_SQL, {"course_id": course_id})).all()
        }
    return [address[chunk.chunk_id] for chunk in chunks]


class TestReingestOrderStability:
    """Aynı materyalin iki yüklemesi aynı sırayı vermeli."""

    async def test_equal_ranked_chunks_keep_order_across_reingest(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("fts-determinism@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        first_course = await create_course(client, ayse, "COME301")
        second_course = await create_course(client, ayse, "COME302")

        await ingest_same_material(
            worker_engine,
            course_id=first_course,
            uploaded_by=ayse_id,
            document_ids=FIRST_INGEST_IDS,
        )
        await ingest_same_material(
            worker_engine,
            course_id=second_course,
            uploaded_by=ayse_id,
            document_ids=SECOND_INGEST_IDS,
        )

        # Kurgu denetimi: belge kimliklerinin sıralaması gerçekten ters dönmeli.
        # Dönmediyse test kimliğe bağımlılığı hiç zorlamaz ve sessizce yeşil kalır.
        assert (FIRST_INGEST_IDS[0] < FIRST_INGEST_IDS[1]) is not (
            SECOND_INGEST_IDS[0] < SECOND_INGEST_IDS[1]
        ), "kurgu bozulmuş: iki yüklemede belge UUID sıralaması aynı"

        first = await search_addresses(ayse_id, first_course, limit=10)
        second = await search_addresses(ayse_id, second_course, limit=10)

        assert len(first) == sum(len(passages) for _, passages in MATERIAL)
        assert first == second, (
            "aynı materyalin iki yüklemesi farklı sıra verdi — eşitlik bozma "
            "içerikten değil üretilen kimlikten türüyor"
        )

    async def test_equal_ranked_chunks_have_tied_rank(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Kurgunun ikinci denetimi: `ts_rank` gerçekten eşit mi.

        Eşit değilse sıra hiç eşitlik bozmaya düşmez ve yukarıdaki test kimliğe
        bağımlılığı ölçtüğünü sanarak hiçbir şey ölçmez. Ayrı bir test olarak
        duruyor çünkü kırıldığında söylediği şey farklı: kusur kodda değil,
        materyalde.
        """
        ayse_id = await users.create("fts-tie@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        course_id = await create_course(client, ayse, "COME303")
        await ingest_same_material(
            worker_engine,
            course_id=course_id,
            uploaded_by=ayse_id,
            document_ids=FIRST_INGEST_IDS,
        )

        async with rls_session(ayse_id) as session:
            chunks = await fts_search(session, course_id=course_id, query="semafor", limit=10)

        assert len(chunks) == 4
        assert len({round(chunk.fts_score, 9) for chunk in chunks}) == 1

    async def test_limit_selects_the_same_chunks_across_reingest(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """`LIMIT` eşitliğin ortasından kesiyorsa SEÇİLEN küme de aynı kalmalı.

        Bu, sıradan daha zor bir iddiadır: aday kümesini daraltan iç sorgunun
        kendisi de içerikten türeyen bir anahtarla sıralanmadıkça, eşit skorlu
        grubun hangi yarısının pencereye gireceği yüklemeye göre değişir. Dense
        tarafı bu sınırı açıkça kabul ediyor (`dense.py` modül başlığı); FTS'te
        iç pencere istenen sonuç sayısının ta kendisi olduğu için kabul edilemez.
        """
        ayse_id = await users.create("fts-limit@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        first_course = await create_course(client, ayse, "COME304")
        second_course = await create_course(client, ayse, "COME305")

        await ingest_same_material(
            worker_engine,
            course_id=first_course,
            uploaded_by=ayse_id,
            document_ids=FIRST_INGEST_IDS,
        )
        await ingest_same_material(
            worker_engine,
            course_id=second_course,
            uploaded_by=ayse_id,
            document_ids=SECOND_INGEST_IDS,
        )

        first = await search_addresses(ayse_id, first_course, limit=2)
        second = await search_addresses(ayse_id, second_course, limit=2)

        assert len(first) == 2, "pencere eşit skorlu dördün ortasından kesmeli"
        assert first == second, (
            "aynı materyalin iki yüklemesinde pencereye farklı parçalar girdi — "
            "aday seçimi üretilen kimliğe bağlı"
        )
