"""Sohbet sözleşmeleri — modelin üretmesi gereken tipli çıktı ve istemciye dönen zarf (T010).

Burada üç ayrı şema yaşar ve karıştırılmamaları önemlidir:

* `LlmAnswerPayload` — **modelin** üretmek zorunda olduğu JSON. Serbest metin yerine
  tipli çıktı istememizin sebebi ARCHITECTURE §5'tir: bozuk çıktı bir kez retry alır,
  yine bozuksa abstention'a düşer. Yani şema, modeli hizada tutan bir kapıdır.
* `ChatResponse` — **istemciye** dönen zarf. Dosya adı, konum ve alıntı burada
  bulunur ama bunları model YAZMAZ; `RetrievedChunk` metadata'sından üretilirler
  (Anayasa I). Model yalnız hangi `chunk_id`'ye dayandığını söyler.
* `ChatRequest` — istemciden gelen istek.

`AnswerStatus`, `ChatMode` ve `SocraticStage` `app/contracts.py`'de tanımlıdır ve
burada yeniden tanımlanmaz; iki ayrı enum, iki modülün sessizce ayrışması demektir.

Not (gruba): ARCHITECTURE §5 atıf şemasında bir `claim` alanı var ama
`contracts.Citation` yalnız `chunk_id/file_name/location/quote` taşıyor. Sözleşme
dosyası yalnız lider tarafından değiştirildiği için `claim` burada zarf katmanında,
`to_chat_response(..., claims=...)` üzerinden taşınıyor. Guardrail kararları claim'e
bakmaz, yani bu ayrım hiçbir güvenlik kontrolünü etkilemez.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import (
    AnswerStatus,
    ChatMode,
    GeneratedAnswer,
    RetrievedChunk,
    SocraticStage,
)

#: Soru uzunluğu üst sınırı (FR-035). Sınır burada tanımlıdır ki chat ucu (T019) ve
#: üretim servisi aynı sayıyı iki yerde hatırlamak zorunda kalmasın (Anayasa XI).
MAX_QUESTION_LENGTH = 2_000

#: Atıfın yanında gösterilen kaynak alıntısının azami uzunluğu. Alıntı chunk
#: metninden kesilir; modelin yazdığı metinden ASLA alınmaz.
SNIPPET_LENGTH = 240


# ---------------------------------------------------------------------------
# İstek
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Sohbet isteği.

    `socratic_stage` bilinçli olarak YOKTUR: kademe ilerletme kararı istemcide
    değil, sunucudaki state machine'de verilir (spec FR-014). İstemci kademe
    seçebilseydi öğrenci tek istekle `EXPLAIN_WITH_SOURCE` isteyip merdiveni
    atlardı.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=MAX_QUESTION_LENGTH)
    mode: ChatMode = ChatMode.QA
    #: Var olan oturuma devam; yoksa sunucu yeni oturum açar.
    session_id: UUID | None = None
    #: Sokratik modda öğrencinin kendi denemesi. Denemesiz kademe ilerlemez.
    student_attempt: str | None = Field(default=None, max_length=MAX_QUESTION_LENGTH)


# ---------------------------------------------------------------------------
# Model çıktısı — LLM'in üretmek ZORUNDA olduğu şekil
# ---------------------------------------------------------------------------


class LlmCitation(BaseModel):
    """Modelin verdiği atıf: yalnız kimlik ve hangi iddiayı desteklediği.

    Dosya adı ya da sayfa numarası istemiyoruz. İsteseydik model uydurabilirdi ve
    uydurmayı yakalamanın deterministik bir yolu olmazdı; oysa `chunk_id`
    set-membership ile sınanabilir.
    """

    model_config = ConfigDict(extra="ignore")

    chunk_id: UUID
    claim: str = ""


class LlmHint(BaseModel):
    """Sokratik ipucu. Kaynaksız ipucu yoktur — `chunk_id` zorunludur (Anayasa I)."""

    model_config = ConfigDict(extra="ignore")

    text: str
    chunk_id: UUID


class LlmAnswerPayload(BaseModel):
    """Modelin döndürmesi gereken JSON gövdesi.

    `extra="ignore"`: konuşkan bir modelin fazladan anahtar eklemesi cevabı
    çöpe atmaya değmez. Buna karşılık ANLAM taşıyan kurallar (cevap verdiğini
    söyleyip boş metin dönmek gibi) aşağıdaki doğrulayıcıda reddedilir —
    reddedilen çıktı retry'a, ısrar eden çıktı abstention'a gider.
    """

    model_config = ConfigDict(extra="ignore")

    status: AnswerStatus
    answer: str = ""
    citations: list[LlmCitation] = Field(default_factory=list)
    hints: list[LlmHint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _answered_needs_content(self) -> LlmAnswerPayload:
        """`answered` diyip elinde ne metin ne ipucu olan çıktı geçersizdir.

        Bu boş bir biçim kontrolü değil: "cevapladım" deyip boş dönen bir çıktı,
        zincirin ilerisinde kaynaksız bir cevaba dönüşürdü. Burada reddetmek
        fail-closed davranışın en ucuz noktasıdır.
        """
        if self.status is AnswerStatus.BUDGET_EXHAUSTED:
            raise ValueError("budget_exhausted yalnız sunucu politika kapısı tarafından üretilir")
        if self.status is AnswerStatus.ANSWERED and not self.answer.strip():
            if not any(hint.text.strip() for hint in self.hints):
                raise ValueError("answered durumunda boş cevap metni kabul edilmez")
        return self


# ---------------------------------------------------------------------------
# İstemciye dönen zarf
# ---------------------------------------------------------------------------


class CitationOut(BaseModel):
    """Kullanıcıya gösterilen atıf.

    `file_name`, `location` ve `snippet` chunk metadata'sından gelir. Modelin
    metninden türetilen tek alan `claim`'dir ve o da yalnız açıklayıcıdır —
    hiçbir güvenlik kararı ona bakmaz.
    """

    chunk_id: UUID
    claim: str = ""
    file_name: str
    location: str
    snippet: str


class HintOut(BaseModel):
    """Sokratik ipucu. Kaynağı olmayan ipucu istemciye hiç ulaşmaz."""

    text: str
    chunk_id: UUID
    file_name: str
    location: str
    stage: SocraticStage | None = None


class ChatResponse(BaseModel):
    """ARCHITECTURE §5 cevap zarfı.

    Abstention bir HATA DEĞİLDİR: `insufficient_context`, `out_of_scope` ve
    `budget_exhausted` normal 200 gövdesiyle döner (Anayasa VII — abstention
    hata gibi gösterilmez).
    Sağlayıcı/model adı bilinçli olarak dışarı verilmez; altyapı ayrıntısı
    kullanıcıya gitmez, ölçüm için `GeneratedAnswer` üzerinde loglanır.

    `session_id`/`message_id` zarfın parçasıdır ve opsiyonel DEĞİLDİR: istemci bir
    sonraki turu aynı oturuma bağlamak zorundadır ve oturum kimliğini kendisi
    uyduramaz. 9 Ağustos'a kadar bu iki alan yalnız `api/chat.py`'nin geçici
    kopyasında vardı; zarfın iki ayrı tanımı olması istemciyi hiçbir zaman
    koşmamış bir sözleşmeye karşı yazdırdı (bkz. modül docstring'i).
    """

    session_id: UUID
    message_id: UUID
    status: AnswerStatus
    mode: ChatMode
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    hints: list[HintOut] = Field(default_factory=list)
    socratic_stage: SocraticStage | None = None
    #: Cevap birebir eşleşmeli önbellekten geldi mi (FR-034). Ölçüm için taşınır.
    cached: bool = False


def snippet_of(chunk: RetrievedChunk, limit: int = SNIPPET_LENGTH) -> str:
    """Chunk metninden gösterilecek alıntıyı keser.

    Tek yerde durur çünkü alıntının nereden geldiği bir ürün kararıdır: her
    çağıran kendi kesme kuralını yazsaydı, biri er geç model metnini alıntı
    sanıp gösterirdi (Anayasa I + XI).
    """
    text = " ".join(chunk.text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def to_chat_response(
    answer: GeneratedAnswer,
    *,
    session_id: UUID,
    message_id: UUID,
    claims: Mapping[UUID, str] | None = None,
    cached: bool = False,
) -> ChatResponse:
    """`GuardrailVerdict`'lerden GEÇMİŞ bir cevabı istemci zarfına çevirir.

    Sokratik modda ipucu ayrı bir alan olarak sunulur ama ayrı bir metin değildir:
    merdivenin her kademesinde tek ipucu verilir, o da cevabın kendisidir. Bunu
    burada türetmek, ipucunun kaynak doğrulamasından ayrı bir yol izlemesini
    imkânsız kılar — tek atıf kümesi, tek kontrol (Anayasa XI).
    """
    claims = claims or {}
    citations = [
        CitationOut(
            chunk_id=citation.chunk_id,
            claim=claims.get(citation.chunk_id, ""),
            file_name=citation.file_name,
            location=citation.location,
            snippet=citation.quote,
        )
        for citation in answer.citations
    ]

    hints: list[HintOut] = []
    if (
        answer.mode is ChatMode.SOCRATIC
        and answer.status is AnswerStatus.ANSWERED
        and answer.citations
        and answer.text.strip()
    ):
        source = answer.citations[0]
        hints.append(
            HintOut(
                text=answer.text,
                chunk_id=source.chunk_id,
                file_name=source.file_name,
                location=source.location,
                stage=answer.socratic_stage,
            )
        )

    return ChatResponse(
        session_id=session_id,
        message_id=message_id,
        status=answer.status,
        mode=answer.mode,
        answer=answer.text,
        citations=citations,
        hints=hints,
        socratic_stage=answer.socratic_stage,
        cached=cached,
    )
