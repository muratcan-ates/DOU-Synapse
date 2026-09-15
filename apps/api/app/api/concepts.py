"""Kavram haritası uçları — materyalden çıkarılan terimler ve bağlantıları.

## Neden bu uç bir "cevap" ucu değil

Burada model çağrılmaz, jeton harcanmaz ve hiçbir cümle üretilmez. Uç, dersin
işlenmiş pasajlarından terimleri sayar ve her terimi geçtiği pasaja bağlar —
yani bir DİZİN üretir. "Kaynak yoksa cevap yok" ilkesi burada en katı hâliyle
uygulanır: gösterilen her satırın arkasında birebir bir chunk vardır.

## Neden sınav kilidine bağlı

Dönen `SourceRefOut` materyalin kendisini (alıntıyı) taşır. Yürüyen bir sınavda
öğrenciye materyal alıntısı açmak, sınav bütünlüğünü delerdi; bu yüzden uç
`UnlockedCourseMemberDep` kullanır ve kilit sunucuda uygulanır. Arayüzün kilidi
ayrıca okuması yalnız kullanıcıya sebebini söylemek içindir.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, UnlockedCourseMemberDep
from app.models.core import Course
from app.modules.assessment.grading import load_source_material
from app.modules.retrieval.concepts import ConceptMap, build_concept_map
from app.schemas.concepts import ConceptEdgeOut, ConceptMapOut, ConceptTermOut

router = APIRouter(prefix="/courses/{course_id}/concepts", tags=["concepts"])

#: Dosya adı ASCII: `Content-Disposition` başlığında Türkçe karakter
#: tarayıcıdan tarayıcıya farklı çözülüyor ve dosya adı bozuk iniyor.
_EXPORT_PREFIX = "kavram-haritasi"


async def _map_out(
    session: AsyncSession, course_id: UUID, concept_map: ConceptMap
) -> ConceptMapOut:
    """Haritayı kaynak referanslarıyla zenginleştirir.

    Alıntı `focus=term` ile seçilir: aynı chunk iki terim için farklı cümlelerle
    gösterilir ve her terim kendi bağlamını görür. Malzeme TEK sorguda okunur —
    terim başına ayrı sorgu atılmaz.
    """
    materials = await load_source_material(session, [term.chunk_id for term in concept_map.terms])
    terms = [
        ConceptTermOut(
            key=term.key,
            term=term.surface,
            chunk_count=term.chunk_count,
            source=material.reference(focus=term.surface),
        )
        for term in concept_map.terms
        # Malzemesi okunamayan terim atlanır: kaynağı gösterilemeyen bir satır
        # tam olarak bu ekranın vaat etmediği şeydir.
        if (material := materials.get(term.chunk_id)) is not None
    ]
    gecerli = {term.key for term in terms}
    return ConceptMapOut(
        course_id=course_id,
        terms=terms,
        edges=[
            ConceptEdgeOut(left=edge.left, right=edge.right, chunk_count=edge.chunk_count)
            for edge in concept_map.edges
            if edge.left in gecerli and edge.right in gecerli
        ],
        chunk_count=concept_map.chunk_count,
        truncated=concept_map.truncated,
    )


@router.get("", response_model=ConceptMapOut)
async def course_concepts(
    context: UnlockedCourseMemberDep,
    session: SessionDep,
) -> ConceptMapOut:
    """Dersin kavram haritası: terimler, kaynakları ve birlikte geçme bağları."""
    concept_map = await build_concept_map(session, context.course_id)
    return await _map_out(session, context.course_id, concept_map)


def render_markdown(course_code: str, data: ConceptMapOut) -> str:
    """İndirilebilir özet.

    Biçim bilinçli olarak sade: her terim bir başlık, altında materyaldeki
    alıntı ve konumu. Yorum satırı yok — bu dosya bir ders notu değil, bir
    kaynak dizinidir ve öyle okunmalı.
    """
    stamp = datetime.now(UTC).strftime("%d.%m.%Y")
    isim = {term.key: term.term for term in data.terms}
    satirlar = [
        f"# {course_code} — kavram haritası",
        "",
        f"DOU-Synapse · CourseGPT · {stamp}",
        "",
        f"Bu dosya dersin {data.chunk_count} materyal pasajından çıkarıldı. "
        "Her terim materyalde gerçekten geçtiği yere bağlıdır; yapay zekâ yorumu "
        "ya da tanımı eklenmemiştir.",
    ]
    if data.truncated:
        satirlar += ["", "> Not: materyal sınırı aşıldığı için pasajların bir kısmı okunmadı."]

    satirlar += ["", "## Parçalar", ""]
    for sira, term in enumerate(data.terms, start=1):
        satirlar += [
            f"### {sira}. {term.term}",
            "",
            f"{term.chunk_count} pasajda geçiyor · {term.source.file_name}"
            f" · {term.source.location}",
            "",
            f"> {term.source.snippet}",
            "",
        ]

    satirlar += ["## Bağlantılar", "", "Aynı pasajda birlikte anlatılan terimler:", ""]
    if data.edges:
        satirlar += ["| Terim | Terim | Kaç pasajda birlikte |", "|---|---|---|"]
        satirlar += [
            f"| {isim[edge.left]} | {isim[edge.right]} | {edge.chunk_count} |"
            for edge in data.edges
        ]
    else:
        satirlar.append("Yeterli veri yok.")
    return "\n".join(satirlar) + "\n"


@router.get("/export")
async def export_concepts(
    context: UnlockedCourseMemberDep,
    session: SessionDep,
) -> Response:
    """Kavram haritasını Markdown olarak indirir. PDF üretilmez (bağımlılık gerekirdi)."""
    concept_map = await build_concept_map(session, context.course_id)
    data = await _map_out(session, context.course_id, concept_map)
    # Ders kodu başlıkta geçiyor; üyelik bağlamı taşımadığı için tek alan okunur.
    code = await session.scalar(select(Course.code).where(Course.id == context.course_id))
    gun = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content=render_markdown(code or "Ders", data),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_EXPORT_PREFIX}-{gun}.md"',
        },
    )
