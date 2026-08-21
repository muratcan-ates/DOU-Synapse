"""Guardrail zinciri — sıra burada, tek yerde kurulur.

ARCHITECTURE §5 sırası SABİTTİR: generation → citation → leakage → sanitize.
Sıranın tek yerde durmasının sebebi, çağıranların (Şerit 3 chat ucu, Şerit 4
sınav akışı) halkaları kendi elleriyle dizmesini engellemektir. Üç çağıran üç
kez dizerse, biri er geç sanitize'ı atlar ya da citation'ı leakage'dan sonraya
alır — ve bu hata sessizdir: sistem çalışmaya devam eder, yalnız garantisi
kalmaz.

Sıra neden bu:

* **citation önce** çünkü kaynağı doğrulanmamış bir metni pedagojik olarak
  incelemenin anlamı yok; zaten gösterilmeyecek.
* **leakage ortada** çünkü yeniden üretimi (regen) tetikleyen tek halka odur ve
  regen sonrası cevabın atıfları YENİDEN doğrulanmalıdır — yeni cevap, yeni
  atıflar demektir.
* **sanitize sonda** çünkü metni değiştiren tek halka odur; ondan sonra bir
  denetim koysaydık, denetlenen metin gönderilen metin olmazdı.

Fail-closed davranış: pedagojik ihlalde bir kez yeniden üretilir, ısrar ederse
şablon ipucuna düşülür. Sınav modunda ipucu tamamen kapalı olduğu için şablon
yolu da yoktur; orada ihlal doğrudan bloklanır.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from uuid import UUID

from app.contracts import (
    AnswerStatus,
    ChatMode,
    GeneratedAnswer,
    Generator,
    Guardrail,
    GuardrailVerdict,
    RetrievedChunk,
    SocraticStage,
)
from app.core.logging import get_logger
from app.modules.generation.service import USER_TEXT
from app.modules.guardrails import leakage
from app.modules.guardrails.citation import (
    BLOCK_REASON_NO_VALID_CITATION,
    CitationGuardrail,
    drop_invalid,
)
from app.modules.guardrails.leakage import LeakageGuardrail
from app.modules.guardrails.sanitize import SanitizeGuardrail

logger = get_logger("app.guardrails")

_CITATION = CitationGuardrail()
_LEAKAGE = LeakageGuardrail()
_SANITIZE = SanitizeGuardrail()


@dataclass(slots=True)
class ScreenOutcome:
    """Zincirin bir turdan çıkan hâli."""

    answer: GeneratedAnswer
    verdicts: list[GuardrailVerdict] = field(default_factory=list)
    block_reason: str | None = None

    @property
    def blocked(self) -> bool:
        return self.block_reason is not None

    @property
    def dropped_citations(self) -> list[UUID]:
        return [c for verdict in self.verdicts for c in verdict.dropped_citations]


@dataclass(slots=True)
class PipelineResult:
    """Uçtan uca sonuç.

    `blocked` ve `block_reason`, `status` alanından AYRI taşınır. Sebep ölçmedir
    (Anayasa III): "materyalde kanıt yoktu" ile "cevap üretildi ama guardrail
    geçirmedi" kullanıcıya aynı görünür, ama değerlendirme için bambaşka iki
    olaydır. Tek alana sıkıştırılsalardı sızıntı oranı hiç ölçülemezdi.
    """

    answer: GeneratedAnswer
    claims: dict[UUID, str] = field(default_factory=dict)
    verdicts: list[GuardrailVerdict] = field(default_factory=list)
    block_reason: str | None = None
    regenerated: bool = False
    used_template_hint: bool = False

    @property
    def blocked(self) -> bool:
        return self.block_reason is not None


#: ARCHITECTURE §5 sırası — TEK KAYNAK. Çağıranlar bu sırayı yeniden dizmez.
GUARDRAIL_CHAIN: tuple[Guardrail, ...] = (_CITATION, _LEAKAGE, _SANITIZE)


def screen(
    answer: GeneratedAnswer,
    chunks: list[RetrievedChunk],
    chain: Sequence[Guardrail] = GUARDRAIL_CHAIN,
) -> ScreenOutcome:
    """Zinciri bir cevap üzerinde koşturur. LLM ÇAĞIRMAZ — saf fonksiyon.

    Girdi nesnesi değiştirilmez; kararlar bir kopyaya uygulanır. Guardrail
    testlerinin çoğu doğrudan bu fonksiyonu çağırır: sınanan şey zincir, model
    değil.

    `chain` parametresi 9 Ağustos birleştirmesinde eklendi. Şerit 3, bu modül
    henüz yokken kendi uygulayıcısını yazmıştı ve testlerinde tek bir halka
    enjekte ediyordu; iki uygulayıcı aynı işi yapıyordu (Anayasa XI). Kopya
    silindi, enjeksiyon buraya taşındı: sıra hâlâ tek yerde, ama bir çağıran
    daraltılmış bir zincirle sınanabiliyor.
    """
    current = replace(answer, citations=list(answer.citations))
    verdicts: list[GuardrailVerdict] = []

    for guard in chain:
        verdict = guard.check(current, chunks)
        verdicts.append(verdict)

        if verdict.dropped_citations:
            current.citations = drop_invalid(current.citations, verdict.dropped_citations)
            logger.warning(
                "doğrulanmamış atıf düştü",
                extra={
                    "context": {
                        "dropped": [str(c) for c in verdict.dropped_citations],
                        "mode": current.mode.value,
                    }
                },
            )
        if verdict.sanitized_text is not None:
            current.text = verdict.sanitized_text
        if verdict.blocked:
            # Bloklanan cevabı sonraki halkalar "düzeltemez"; zincir burada durur.
            return ScreenOutcome(current, verdicts, verdict.reason)

    return ScreenOutcome(current, verdicts)


def is_leakage_block(reason: str | None) -> bool:
    return bool(reason) and reason.startswith(f"{leakage.REASON_PREFIX}:")  # type: ignore[union-attr]


def blocked_answer(
    reason: str | None,
    *,
    mode: ChatMode,
    socratic_stage: SocraticStage | None = None,
) -> GeneratedAnswer:
    """Bloklanan cevabın yerine geçen, kaynaksız ama dürüst metin.

    Statü `insufficient_context`: kullanıcı açısından sonuç "güvenle
    cevaplayamadım"dır ve bu bir HATA DEĞİLDİR (Anayasa VII — ret hata gibi
    gösterilmez). Bloklama sebebi `PipelineResult.block_reason` alanında ayrıca
    taşınır, böylece ölçüm gerçek abstention ile bloklamayı karıştırmaz.
    """
    if reason == BLOCK_REASON_NO_VALID_CITATION:
        key = "blocked_no_citation"
    elif mode is ChatMode.EXAM and is_leakage_block(reason):
        key = "blocked_exam_hint"
    else:
        key = "blocked_generic"
    return GeneratedAnswer(
        status=AnswerStatus.INSUFFICIENT_CONTEXT,
        mode=mode,
        text=USER_TEXT[key],
        citations=[],
        socratic_stage=socratic_stage,
    )


class AnswerPipeline:
    """Üretim + guardrail zinciri. Çağıranların gördüğü tek yüzey."""

    def __init__(self, generator: Generator) -> None:
        self._generator = generator

    async def run(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        student_attempt: str | None = None,
    ) -> PipelineResult:
        answer, claims = await self._generate(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=socratic_stage,
            student_attempt=student_attempt,
            strict_retry=False,
        )
        outcome = screen(answer, chunks)

        if not outcome.blocked:
            return PipelineResult(outcome.answer, claims, outcome.verdicts)

        if not is_leakage_block(outcome.block_reason):
            return _blocked_result(outcome, mode, socratic_stage, claims)

        # Sınavda ipucu kapalı: yeniden üretmenin hedefi olmadığı için regen yok.
        if mode in leakage.NO_FALLBACK_MODES:
            logger.warning(
                "sınav modunda sızıntı bloklandı",
                extra={"context": {"reason": outcome.block_reason}},
            )
            return _blocked_result(outcome, mode, socratic_stage, claims)

        logger.warning(
            "pedagojik ihlal — yeniden üretiliyor",
            extra={"context": {"reason": outcome.block_reason, "mode": mode.value}},
        )
        retry_answer, retry_claims = await self._generate(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=socratic_stage,
            student_attempt=student_attempt,
            strict_retry=True,
        )
        retry_outcome = screen(retry_answer, chunks)
        if not retry_outcome.blocked:
            return PipelineResult(
                retry_outcome.answer, retry_claims, retry_outcome.verdicts, regenerated=True
            )

        # Israr: deterministik son durak. Model devre dışı, metin sabit.
        template = leakage.build_template_hint(chunks, socratic_stage=socratic_stage)
        if template is None:
            return _blocked_result(retry_outcome, mode, socratic_stage, retry_claims, True)

        template_outcome = screen(template, chunks)
        if template_outcome.blocked:
            # Şablonun kendisi zincirden geçemiyorsa gösterecek bir şey yok.
            logger.error(
                "şablon ipucu zincirden geçemedi",
                extra={"context": {"reason": template_outcome.block_reason}},
            )
            return _blocked_result(template_outcome, mode, socratic_stage, {}, True)

        logger.warning(
            "pedagojik ihlal sürdü — şablon ipucuna düşüldü",
            extra={"context": {"reason": retry_outcome.block_reason}},
        )
        return PipelineResult(
            template_outcome.answer,
            {},
            retry_outcome.verdicts + template_outcome.verdicts,
            regenerated=True,
            used_template_hint=True,
        )

    async def _generate(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None,
        student_attempt: str | None,
        strict_retry: bool,
    ) -> tuple[GeneratedAnswer, dict[UUID, str]]:
        """Üreticiyi çağırır; sunum verisini destekliyorsa onu da alır.

        `claims`, sözleşmede yeri olmayan sunum alanıdır (bkz. `GenerationResult`).
        Şerit 3 ve 4'ün testlerinde kullanacağı sahte üreticiler yalnız
        `Generator` protokolünü uygular; onlarda bu alan boş kalır ve zincir
        aynı şekilde çalışır.
        """
        detailed = getattr(self._generator, "generate_with_claims", None)
        if detailed is not None:
            result = await detailed(
                question=question,
                chunks=chunks,
                mode=mode,
                socratic_stage=socratic_stage,
                student_attempt=student_attempt,
                strict_retry=strict_retry,
            )
            return result.answer, result.claims
        answer = await self._generator.generate(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=socratic_stage,
        )
        return answer, {}


def _blocked_result(
    outcome: ScreenOutcome,
    mode: ChatMode,
    socratic_stage: SocraticStage | None,
    claims: dict[UUID, str],
    regenerated: bool = False,
) -> PipelineResult:
    del claims  # bloklanan cevabın atıfı gösterilmez, dolayısıyla iddiası da
    return PipelineResult(
        answer=blocked_answer(outcome.block_reason, mode=mode, socratic_stage=socratic_stage),
        claims={},
        verdicts=outcome.verdicts,
        block_reason=outcome.block_reason,
        regenerated=regenerated,
    )
