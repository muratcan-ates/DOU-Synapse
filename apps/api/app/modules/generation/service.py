"""Üretim servisi — `Generator` protokolünün uygulaması (T012).

Akış: prompt kur → LLM çağır → Pydantic doğrula → bozuksa retry → yine bozuksa
abstention.

Buradaki asıl mesele "model sayı uydurmaz" ilkesinin başladığı yerdir. Model
yalnızca hangi `chunk_id`'ye dayandığını söyler; dosya adı, sayfa numarası ve
alıntı `RetrievedChunk` metadata'sından doldurulur (`guardrails.citation.build_citations`).
Modelin yazdığı bir sayfa numarasını gösterseydik, "kaynaklı" görünen ama
uydurulmuş bir referans üretmiş olurduk — kullanıcı açısından en kötü hata türü,
çünkü yanlış olduğunu anlamanın yolu yok.

İkinci mesele fail-closed sıralamasıdır:

* Chunk yoksa LLM HİÇ çağrılmaz. Kanıt yokken model çağırmak hem kota harcar hem
  de modele "boşluğu doldur" davetiyesi çıkarır.
* Bozuk çıktı `llm_max_retries` kadar yeniden denenir, sonra abstention'a düşer.
* Sağlayıcıya ulaşılamaması abstention DEĞİLDİR: `LlmUnavailableError` yukarı
  gider. "Kaynak bulamadım" ile "servise ulaşamadım" farklı şeylerdir ve
  ikincisini birincisi gibi saymak SC-005 ret oranını sahte biçimde şişirir.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from pydantic import ValidationError

from app.contracts import (
    AnswerStatus,
    ChatMode,
    GeneratedAnswer,
    RetrievedChunk,
    SocraticStage,
)
from app.core.config import Settings, get_settings
from app.core.llm_json import first_json_object
from app.core.logging import get_logger
from app.modules.generation import prompts
from app.modules.generation.llm import LlmClient, build_llm_client
from app.modules.guardrails.citation import build_citations
from app.schemas.chat import LlmAnswerPayload, LlmCitation

logger = get_logger("app.generation")

#: Kullanıcıya dönen sabit metinler tek sözlükte yaşar. Her modülün kendi
#: "üzgünüm, cevap veremiyorum" cümlesini yazması, aynı ürünün üç farklı ses
#: tonuyla konuşması demektir (Anayasa V + XI).
USER_TEXT: dict[str, str] = {
    "insufficient_context": (
        "Bu soruyu ders materyalinde bulabildiğim kaynaklarla güvenle cevaplayamıyorum. "
        "Soruyu biraz daha somutlaştırırsan tekrar deneyebilirim."
    ),
    "out_of_scope": (
        "Bu konu dersin kapsamı dışında görünüyor. "
        "Ders materyalindeki bir konuyu sorarsan yardımcı olabilirim."
    ),
    "blocked_no_citation": (
        "Bu soruya ders materyalinden doğrulanmış bir kaynak gösteremediğim için "
        "cevabı paylaşmıyorum. Kaynağı olmayan bir cevap vermemeyi tercih ederim."
    ),
    "blocked_exam_hint": (
        "Sınav sürerken ipucu veya çözüm paylaşılmaz. Geri bildirimi sınav bittiğinde görebilirsin."
    ),
    "blocked_generic": (
        "Bu cevabı güvenlik kontrollerinden geçiremedim, bu yüzden paylaşmıyorum. "
        "Soruyu farklı biçimde sorarsan tekrar deneyebilirim."
    ),
}

_REPAIR_NOTE = """

ÖNCEKİ DENEMEN GEÇERSİZDİ. Yanıtın tek bir JSON nesnesi olmalıydı ve olmadı.
Bu sefer yalnızca JSON döndür: metin, açıklama veya kod çiti ekleme."""


@dataclass(slots=True)
class GenerationResult:
    """Üretim çıktısı + sözleşmede yeri olmayan sunum verisi.

    `claims` neden burada: ARCHITECTURE §5 atıf şemasında bir `claim` alanı var
    ama `contracts.Citation`'da yok ve sözleşme dosyasını yalnız lider
    değiştirebiliyor. Alan sunum amaçlıdır — hiçbir guardrail kararı ona bakmaz —
    bu yüzden sözleşmeyi zorlamak yerine zarf katmanına kadar burada taşınıyor.
    """

    answer: GeneratedAnswer
    claims: dict[UUID, str] = field(default_factory=dict)


class GenerationService:
    """`Generator` protokolünü uygular."""

    def __init__(
        self,
        llm: LlmClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm if llm is not None else build_llm_client(self._settings)

    async def generate(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        student_attempt: str | None = None,
    ) -> GeneratedAnswer:
        result = await self.generate_with_claims(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=socratic_stage,
            student_attempt=student_attempt,
        )
        return result.answer

    async def generate_with_claims(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        student_attempt: str | None = None,
        strict_retry: bool = False,
    ) -> GenerationResult:
        if not chunks:
            # Kanıt yokken modeli çağırmak, boşluğu doldurmasını istemektir.
            return GenerationResult(
                answer=_abstain(AnswerStatus.INSUFFICIENT_CONTEXT, mode, socratic_stage)
            )

        request = prompts.build_request(
            question,
            chunks,
            mode=mode,
            socratic_stage=socratic_stage,
            student_attempt=student_attempt,
            strict_retry=strict_retry,
        )

        payload: LlmAnswerPayload | None = None
        provider: str | None = None
        model: str | None = None

        for attempt in range(self._settings.llm_max_retries + 1):
            current = (
                request if attempt == 0 else replace(request, system=request.system + _REPAIR_NOTE)
            )
            completion = await self._llm.complete(current)
            provider, model = completion.provider, completion.model
            payload = _parse_payload(completion.text)
            if payload is not None:
                break
            logger.warning(
                "llm çıktısı şemaya uymadı",
                extra={"context": {"attempt": attempt, "provider": provider, "model": model}},
            )

        if payload is None:
            # Israrla bozuk çıktı: uydurmaya çalışmak yerine kapan (Anayasa IV).
            return GenerationResult(
                answer=_abstain(AnswerStatus.INSUFFICIENT_CONTEXT, mode, socratic_stage)
            )

        return _to_answer(
            payload,
            chunks=chunks,
            mode=mode,
            socratic_stage=socratic_stage,
            provider=provider,
            model=model,
        )


def _abstain(
    status: AnswerStatus, mode: ChatMode, socratic_stage: SocraticStage | None
) -> GeneratedAnswer:
    return GeneratedAnswer(
        status=status,
        mode=mode,
        text=USER_TEXT[status.value],
        citations=[],
        socratic_stage=socratic_stage,
    )


def _to_answer(
    payload: LlmAnswerPayload,
    *,
    chunks: list[RetrievedChunk],
    mode: ChatMode,
    socratic_stage: SocraticStage | None,
    provider: str | None,
    model: str | None,
) -> GenerationResult:
    """Model çıktısını, metadata'dan doldurulmuş cevaba çevirir.

    İpucu kaynakları atıf listesine KATILIR. Bu bilinçli: "kaynaksız ipucu
    gösterilmez" kuralı ayrı bir kontrol olarak yazılsaydı, atıf doğrulamasıyla
    zamanla ayrışırdı. Tek küme, tek kontrol — ipucunun kimliği de aynı
    set-membership kapısından geçer (Anayasa I + XI).
    """
    text = payload.answer.strip()
    if not text and payload.hints:
        text = payload.hints[0].text.strip()

    # Sıra korunur: model neyi önce saydıysa kullanıcı da onu önce görür.
    cited: list[LlmCitation] = list(payload.citations)
    cited.extend(LlmCitation(chunk_id=hint.chunk_id) for hint in payload.hints)

    citations, claims = build_citations(cited, chunks)

    status = payload.status
    if status is AnswerStatus.ANSWERED and not text:
        status = AnswerStatus.INSUFFICIENT_CONTEXT
        text = USER_TEXT[status.value]

    if status is not AnswerStatus.ANSWERED and not text:
        text = USER_TEXT[status.value]

    return GenerationResult(
        answer=GeneratedAnswer(
            status=status,
            mode=mode,
            text=text,
            citations=citations,
            socratic_stage=socratic_stage,
            provider=provider,
            model=model,
        ),
        claims=claims,
    )


def _parse_payload(raw: str) -> LlmAnswerPayload | None:
    """Sağlayıcı metninden şemaya uyan gövdeyi çıkarır.

    Modeller JSON'u kod çiti içine almaya ya da önüne bir cümle koymaya
    meyillidir; `core.llm_json` o gürültüyü tek kuralla kaldırır (aynı kuralı
    soru üretimi ve puanlama da kullanır).
    """
    data = first_json_object(raw)
    if data is None:
        return None
    try:
        return LlmAnswerPayload.model_validate(data)
    except ValidationError:
        return None
