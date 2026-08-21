"""Chunking.

İki kural bu modülün tasarımını belirler (ARCHITECTURE.md §3):

1. **Bir chunk iki sayfayı/slaytı birleştirmez.** Aksi halde "sayfa 12-13" gibi bulanık
   bir kaynak göstermek zorunda kalırdık; atıf doğruluğu doğrudan buna bağlı.
2. **Kod blokları mantıksal sınırlarından bölünür.** Yarım fonksiyon, tek başına
   anlamsız bir chunk üretir.

Chunk boyutu ve örtüşme sabit doğrular değil, gold set üzerinde ayarlanacak başlangıç
değerleridir.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from app.models.core import ChunkContentType
from app.modules.ingestion.parsers import ParsedBlock

TARGET_TOKENS = 500
OVERLAP_TOKENS = 75
MIN_TOKENS = 40

# XLM-R (bge-m3) tokenizer'ı Türkçe metinde kabaca 3.5-4 karakter/token üretir. Gerçek
# tokenizer fastembed ile geldiğinde `token_counter` parametresinden geçirilecek;
# chunking mantığı değişmeyecek.
_CHARS_PER_TOKEN = 3.7


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / _CHARS_PER_TOKEN))


TokenCounter = Callable[[str], int]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?:;])\s+|\n{2,}")


@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    token_count: int
    content_type: ChunkContentType
    page_number: int | None
    slide_number: int | None
    section_title: str | None


def _split_units(text: str, content_type: ChunkContentType) -> list[str]:
    """Metni bölünebilir en küçük anlamlı birimlere ayırır."""
    if content_type is ChunkContentType.CODE:
        return text.splitlines(keepends=True) or [text]
    units = [unit for unit in _SENTENCE_SPLIT.split(text) if unit and unit.strip()]
    return units or [text]


def _pack(
    units: Sequence[str],
    *,
    joiner: str,
    token_counter: TokenCounter,
    target: int,
    overlap: int,
) -> list[str]:
    """Birimleri hedef boyuta yakın gruplara toplar, gruplar arasında örtüşme bırakır."""
    groups: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for unit in units:
        unit_tokens = token_counter(unit)

        # Tek başına hedefi aşan birim (çok uzun paragraf veya satır) olduğu gibi kalır;
        # cümle ortasından kesmek, anlamı bozup retrieval'i kötüleştirir.
        if unit_tokens >= target and current:
            groups.append(joiner.join(current))
            current, current_tokens = [], 0

        if current_tokens + unit_tokens > target and current:
            groups.append(joiner.join(current))
            # Örtüşme: son birimleri bir sonraki gruba taşı.
            carried: list[str] = []
            carried_tokens = 0
            for previous in reversed(current):
                previous_tokens = token_counter(previous)
                if carried_tokens + previous_tokens > overlap:
                    break
                carried.insert(0, previous)
                carried_tokens += previous_tokens
            current, current_tokens = carried, carried_tokens

        current.append(unit)
        current_tokens += unit_tokens

    if current:
        groups.append(joiner.join(current))
    return [group for group in (g.strip() for g in groups) if group]


def chunk_blocks(
    blocks: Iterable[ParsedBlock],
    *,
    token_counter: TokenCounter = estimate_tokens,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
    min_tokens: int = MIN_TOKENS,
) -> list[Chunk]:
    """Ayrıştırılmış blokları chunk'lara dönüştürür.

    Bloklar sayfa/slayt sınırında geldiği için, her blok kendi içinde bölünür ve
    chunk'lar hiçbir zaman iki sayfayı kapsamaz.
    """
    chunks: list[Chunk] = []
    pending: Chunk | None = None

    for block in blocks:
        joiner = "" if block.content_type is ChunkContentType.CODE else " "
        units = _split_units(block.text, block.content_type)
        for text in _pack(
            units,
            joiner=joiner,
            token_counter=token_counter,
            target=target_tokens,
            overlap=overlap_tokens,
        ):
            chunk = Chunk(
                text=text,
                token_count=token_counter(text),
                content_type=block.content_type,
                page_number=block.page_number,
                slide_number=block.slide_number,
                section_title=block.section_title,
            )

            # Çok küçük parçalar tek başına anlamsızdır; aynı sayfadaki bir öncekiyle
            # birleştirilir. Farklı sayfadaysa birleştirme YAPILMAZ — kaynak doğruluğu
            # boyut optimizasyonundan önce gelir.
            if (
                pending is not None
                and pending.token_count < min_tokens
                and pending.page_number == chunk.page_number
                and pending.slide_number == chunk.slide_number
                and pending.content_type is chunk.content_type
            ):
                merged_text = f"{pending.text}{joiner}{chunk.text}".strip()
                chunk = Chunk(
                    text=merged_text,
                    token_count=token_counter(merged_text),
                    content_type=chunk.content_type,
                    page_number=chunk.page_number,
                    slide_number=chunk.slide_number,
                    section_title=pending.section_title or chunk.section_title,
                )
                chunks.pop()

            chunks.append(chunk)
            pending = chunk

    return chunks
