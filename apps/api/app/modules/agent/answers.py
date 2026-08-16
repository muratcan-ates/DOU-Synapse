"""Cevap hattı — veritabanından bağımsız, bu yüzden DB'siz test edilebilir.

`app/api/chat.py`'den taşındı (modülerizasyon v2, PR 11): `produce_answer` bir
router değil bir alan servisi — retrieval → kanıt kapısı → generation →
guardrail akışının tek sahibi. Davranış birebir aynı; `chat.py` bu adları
re-export eder (testler ve `evaluation/role_agent_005/offline_fake_eval.py`
`app.api.chat.produce_answer`'ı import etmeye devam eder).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.contracts import (
    AnswerStatus,
    AssistantAudience,
    ChatMode,
    ClaimingGenerator,
    GeneratedAnswer,
    Generator,
    Guardrail,
    RetrievedChunk,
    Retriever,
    RoleAwareClaimingGenerator,
    SocraticStage,
)
from app.core.config import Settings
from app.core.errors import ValidationError
from app.modules.agent.token_precharge import _quota_input_token_ceiling
from app.modules.assessment import socratic
from app.modules.generation import prompts as generation_prompts

# Reddin sözü BİZE aittir, modele değil (Anayasa V + injection savunması): kaynak
# bulunamadığında ya da cevap bloklandığında kullanıcıya modelin ürettiği metin değil
# bu sabitler gider. Materyalin içine gömülmüş bir talimat, ret metnini ele geçiremez.
MESSAGE_INSUFFICIENT_CONTEXT = (
    "Bu soruya ders materyalinde yeterli dayanak bulamadım, bu yüzden cevap vermiyorum. "
    "Soruyu biraz daha somutlaştırıp tekrar denemek ister misin? "
    "Konunun geçtiği hafta ya da kavram adını eklemen genelde yeterli oluyor."
)
MESSAGE_OUT_OF_SCOPE = (
    "Bu soru dersin kapsamı dışında görünüyor. Yalnızca bu derse yüklenmiş "
    "materyallerden cevap verebiliyorum; ders dışı konularda bilerek sessiz kalıyorum."
)
MESSAGE_BLOCKED = (
    "Bir cevap hazırladım ama gösterebileceğim geçerli bir kaynağa bağlayamadım, "
    "bu yüzden paylaşmıyorum. Kaynağı doğrulanmamış cevap vermemeyi tercih ediyorum."
)


def apply_guardrails(
    answer: GeneratedAnswer,
    retrieved: list[RetrievedChunk],
    guardrails: Sequence[Guardrail],
) -> tuple[GeneratedAnswer, bool, list[UUID]]:
    """Zinciri koşturur — uygulama `guardrails.chain.screen()`'e devredilir.

    Bu fonksiyon önce kendi uygulayıcısını taşıyordu: Şerit 2'nin `chain.py`'si
    henüz yokken yazılmıştı ve aynı işi ikinci kez yapıyordu (Anayasa XI).
    9 Ağustos birleştirmesinde gövde silindi; sıra ve halka etkilerinin
    uygulanması artık tek yerde. Burada yalnız çağrı biçimi korunuyor, çünkü
    bu dosyanın testleri daraltılmış bir zincir enjekte ediyor.
    """
    from app.modules.guardrails.chain import screen

    outcome = screen(answer, retrieved, guardrails)
    return outcome.answer, outcome.blocked, outcome.dropped_citations


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    """Bir turun sonucu: cevap + atıf başına iddia metni.

    `claims` ayrı taşınır çünkü `contracts.Citation` bilinçli olarak `claim`
    taşımaz (sözleşme dosyasındaki karara bakın): guardrail hiçbir kararında ona
    bakmaz, dolayısıyla zincirin sözleşmesine girmemesi gerekir. Sunum katmanına
    ulaşması gereken tek yer burasıdır.
    """

    answer: GeneratedAnswer
    claims: dict[UUID, str] = field(default_factory=dict)


def _refusal(
    status_value: AnswerStatus,
    mode: ChatMode,
    text: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> AnswerOutcome:
    return AnswerOutcome(
        GeneratedAnswer(
            status=status_value,
            mode=mode,
            text=text,
            citations=[],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    )


#: Reddin statüsü → kullanıcıya gidecek sabit metin. Sözlük, çağrı yerinde bir
#: if/else zincirinden iyidir: yeni bir ret statüsü eklendiğinde burada eksik
#: kalırsa KeyError verir, sessizce yanlış metin göstermez (fail-closed).
_REFUSAL_TEXT: dict[AnswerStatus, str] = {
    AnswerStatus.OUT_OF_SCOPE: MESSAGE_OUT_OF_SCOPE,
    AnswerStatus.INSUFFICIENT_CONTEXT: MESSAGE_INSUFFICIENT_CONTEXT,
    AnswerStatus.BUDGET_EXHAUSTED: (
        "Bu dersin günlük sohbet AI bütçesi doldu. Bütçe gece yarısı yenilenir."
    ),
}


def _evidence_refusal(
    chunks: list[RetrievedChunk], query: str, threshold: float
) -> AnswerStatus | None:
    """Kanıt kapısı. Cevap üretilebiliyorsa `None`, üretilemiyorsa reddin statüsü.

    Ölçülen birincil sinyal **dense skorudur, füzyon skoru değil.** RRF skoru
    1/(k+sıra) toplamıdır: k=60'ta en iyi sonuç bile ~0.016 çıkar, dolayısıyla
    füzyon skoru sıralama içindir, kalibre edilebilir bir güven ölçüsü değildir.

    Eşiğe burada ikinci kez bakılması bilinçlidir: iki katman da bağımsız olarak
    doğru davranmalıdır (Anayasa II deseni). Eşik `evaluation/calibration.md`'de
    kalibre edildi (0.81); aynı belge holdout'ta hedefi tutturmadığını da yazıyor
    ve sebebin eşiğin değeri değil sinyalin darlığı olduğunu gösteriyor.

    Bu yüzden eşiğin ALTINDA kalan sorgu artık tek bir etikete düşmüyor: kapsam
    dışı sorularla dayanağı zayıf sorular `retrieval.scope` içinde, ölçülmüş
    ikinci ve üçüncü sinyalle ayrılıyor. **Cevaplanan küme değişmez** —
    "yeterli kanıt" koşulu eskisiyle birebir aynı.

    İçeriden import, `get_retriever`/`apply_guardrails` ile aynı desen: modül
    henüz inmemişse uç fail-closed davranır, sessizce cevap üretmez.
    """
    from app.modules.retrieval.scope import assess_evidence

    return assess_evidence(chunks, query=query, threshold=threshold).refusal_status


async def _generate(
    generator: Generator,
    *,
    question: str,
    chunks: list[RetrievedChunk],
    mode: ChatMode,
    stage: SocraticStage | None,
    student_attempt: str | None,
    audience: AssistantAudience,
    max_output_tokens: int,
) -> tuple[GeneratedAnswer, dict[UUID, str]]:
    """Üreteci çağırır ve varsa iddia metinlerini de alır.

    `ClaimingGenerator` uygulayan bir üreteç `generate_with_claims` sunar; sunmayan
    (test ikizleri, sahte üreteç) yalnız `Generator`'ı uygular. Kontrol burada tek
    yerde yapılır, çağıranların her birinde değil.
    """
    if isinstance(generator, RoleAwareClaimingGenerator):
        result = await generator.generate_role_aware_with_claims(
            question=question,
            chunks=chunks,
            mode=mode,
            audience=audience,
            max_output_tokens=max_output_tokens,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        return result.answer, dict(result.claims)

    if isinstance(generator, ClaimingGenerator):
        result = await generator.generate_with_claims(
            question=question,
            chunks=chunks,
            mode=mode,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        return result.answer, dict(result.claims)

    answer = await generator.generate(
        question=question,
        chunks=chunks,
        mode=mode,
        socratic_stage=stage,
        student_attempt=student_attempt,
    )
    return answer, {}


async def produce_answer(
    *,
    question: str,
    course_id: UUID,
    mode: ChatMode,
    decision: socratic.SocraticDecision | None,
    retriever: Retriever,
    generator: Generator,
    guardrails: Sequence[Guardrail],
    settings: Settings,
    student_attempt: str | None = None,
    evidence_threshold: float | None = None,
    audience: AssistantAudience = AssistantAudience.STUDENT,
    max_output_tokens: int = 700,
    before_generation: Callable[[int], Awaitable[None]] | None = None,
    allow_regeneration: bool = True,
) -> AnswerOutcome:
    """Bir turun cevabını üretir. Veritabanına dokunmaz, oturum durumu yazmaz.

    `decision` yalnız Sokratik modda doludur ve kademeyi TAŞIR: servis edilecek kademe
    state machine'in kararıdır, modelin değil. Model kendini bir üst kademeye terfi
    ettiremez.

    `student_attempt` öğrencinin bu turdaki denemesidir ve üretime GEÇİRİLİR: neyi
    yanlış anladığını görmeden verilen ipucu yönlendirme değil tahmindir. 9 Ağustos'a
    kadar alan sözleşmede vardı ama bu uç onu hiç göndermiyordu.
    """
    chunks = await retriever.search(
        course_id=course_id, query=question, limit=settings.retrieval_top_k
    )
    threshold = settings.evidence_threshold if evidence_threshold is None else evidence_threshold
    refusal = _evidence_refusal(chunks, question, threshold)
    if refusal is not None:
        # LLM'e HİÇ gidilmez: kanıt yoksa üretilecek bir şey de yoktur. Kapsam dışı
        # olduğu deterministik olarak saptanmışsa da gidilmez — modele sormak hem
        # kota harcar hem de materyale gömülü bir talimata kapıyı açık bırakırdı.
        return _refusal(refusal, mode, _REFUSAL_TEXT[refusal])

    stage = decision.stage if decision is not None else None

    # Israrcı öğrenci: deneme yapılmadıysa üretim hiç çalıştırılmaz. Kullanıcı nazik
    # uyarıyı ve AYNI kademenin deterministik şablon ipucunu alır — merdiven ilerlemez,
    # kaynak yine taşınır (FR-013/FR-016) ve LLM bütçesi ısrarla tüketilemez.
    if decision is not None and decision.refusal_notice is not None:
        hint_text, citation = socratic.template_hint(decision.stage, chunks[0])
        return AnswerOutcome(
            GeneratedAnswer(
                status=AnswerStatus.ANSWERED,
                mode=mode,
                text=f"{decision.refusal_notice}\n\n{hint_text}",
                citations=[citation],
                socratic_stage=decision.stage,
            )
        )

    try:
        chunks, byte_safe_input_token_ceiling = generation_prompts.fit_chunks_to_input_budget(
            question,
            chunks,
            max_input_bytes=settings.llm_chat_max_input_bytes,
            mode=mode,
            audience=audience,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
    except generation_prompts.PromptBudgetExceeded as exc:
        raise ValidationError(
            "Soru ve deneme, asistanın güvenli bağlam sınırını aşıyor.",
            code="agent_prompt_too_large",
        ) from exc
    if not chunks:
        return _refusal(AnswerStatus.INSUFFICIENT_CONTEXT, mode, MESSAGE_INSUFFICIENT_CONTEXT)

    # Persistent quota is reserved only when this turn will actually reach the
    # provider. Retrieval abstention and the deterministic Socratic template do
    # not hold a two-minute reservation or consume provider budget. The callback
    # receives a reviewed-model token ceiling for known server prompts. Unknown
    # models/prompts retain the provider-independent byte ceiling instead of
    # guessing a divisor or loading a tokenizer on the request path.
    if before_generation is not None:
        quota_request = generation_prompts.build_request(
            question,
            chunks,
            mode=mode,
            audience=audience,
            socratic_stage=stage,
            student_attempt=student_attempt,
        )
        provider_model = settings.llm_primary_model or settings.llm_fallback_model
        input_token_ceiling = _quota_input_token_ceiling(
            quota_request,
            model=provider_model,
            byte_safe_ceiling=byte_safe_input_token_ceiling,
        )
        await before_generation(input_token_ceiling)

    answer, claims = await _generate(
        generator,
        question=question,
        chunks=chunks,
        mode=mode,
        stage=stage,
        student_attempt=student_attempt,
        audience=audience,
        max_output_tokens=max_output_tokens,
    )

    if answer.status is AnswerStatus.OUT_OF_SCOPE:
        return _refusal(
            AnswerStatus.OUT_OF_SCOPE,
            mode,
            MESSAGE_OUT_OF_SCOPE,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )
    if answer.status is AnswerStatus.INSUFFICIENT_CONTEXT:
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_INSUFFICIENT_CONTEXT,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

    # Kademe sunucu otoritesindedir.
    answer.socratic_stage = stage
    answer, blocked, _ = apply_guardrails(answer, chunks, guardrails)

    if blocked and mode is ChatMode.SOCRATIC and allow_regeneration:
        # FR-015: ihlalde BİR kez yeniden üret, sürerse deterministik şablona düş.
        regenerated, claims = await _generate(
            generator,
            question=question,
            chunks=chunks,
            mode=mode,
            stage=stage,
            student_attempt=student_attempt,
            audience=audience,
            max_output_tokens=max_output_tokens,
        )
        regenerated.socratic_stage = stage
        regenerated, blocked, _ = apply_guardrails(regenerated, chunks, guardrails)
        regenerated.prompt_tokens += answer.prompt_tokens
        regenerated.completion_tokens += answer.completion_tokens
        answer = regenerated

    if blocked:
        if mode is ChatMode.SOCRATIC and stage is not None:
            hint_text, citation = socratic.template_hint(stage, chunks[0])
            return AnswerOutcome(
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=mode,
                    text=hint_text,
                    citations=[citation],
                    socratic_stage=stage,
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )
            )
        # QA modunda deterministik bir son durak yoktur: gösterilemeyen cevap
        # gösterilmez (FR-012, fail-closed).
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_BLOCKED,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

    if not answer.citations:
        # Zincir bloklamasa bile kaynaksız akademik cevap kullanıcıya gitmez (FR-013).
        return _refusal(
            AnswerStatus.INSUFFICIENT_CONTEXT,
            mode,
            MESSAGE_BLOCKED,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
        )

    # Düşen atıfların iddiaları da düşer: guardrail bir atıfı elediyse onun iddia
    # metnini taşımak, gösterilmeyen bir kaynağa ait cümleyi ekranda bırakırdı.
    kept = {c.chunk_id for c in answer.citations}
    return AnswerOutcome(answer, {k: v for k, v in claims.items() if k in kept})
