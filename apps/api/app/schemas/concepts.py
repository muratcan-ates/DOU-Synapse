"""Kavram haritası sözleşmeleri.

Her terim bir `SourceRefOut` taşır, yani materyalin KENDİSİNİ. Tipin kendi
belgesi bunu kullanan yüzeyin sınav kilidinden geçmesini şart koşuyor; kavram
haritası ucu bu yüzden `UnlockedCourseMemberDep` ile kapalıdır.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import SourceRefOut


class ConceptTermOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Katlanmış anahtar. Kenarlar bu adla bağlanır; ekranda gösterilmez.
    key: str
    #: Materyaldeki yazım. Ekranda görünen budur.
    term: str
    #: Kaç ayrı pasajda geçtiği — listenin sıralama ölçütü.
    chunk_count: int = Field(ge=1)
    #: Terimin en yoğun geçtiği pasaj. Alıntı chunk'tan birebir gelir.
    source: SourceRefOut


class ConceptEdgeOut(BaseModel):
    """İki terimin kaç pasajı paylaştığı. Anlamsal ilişki iddiası DEĞİL."""

    model_config = ConfigDict(extra="forbid")

    left: str
    right: str
    chunk_count: int = Field(ge=1)


class ConceptMapOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: UUID
    terms: list[ConceptTermOut]
    edges: list[ConceptEdgeOut]
    #: Haritanın dayandığı pasaj sayısı; ekranda "neye bakıldığı" yazılır.
    chunk_count: int = Field(ge=0)
    #: Pasaj sınırı aşıldıysa True — eksik sonuç sessizce sunulmaz.
    truncated: bool = False
