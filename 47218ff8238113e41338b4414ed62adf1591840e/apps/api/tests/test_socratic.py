"""Sokratik merdiven testleri (T028).

Bu dosya **veritabanına ve LLM'e dokunmaz.** Test edilen şey merdivenin kurallarıdır:
kademe ne zaman ilerler, ne zaman ilerlemez, ilerlemediğinde kullanıcı ne görür.
Retrieval ve generation, `app/contracts.py`'deki protokolleri uygulayan sahtelerle
temsil edilir (00_OKU_ONCE §2).

Sahte guardrail bilinçli olarak **gerçek set-membership kontrolünü** yapar: Şerit 2'nin
`citation.py`'si henüz inmediği için, "kaynaksız ipucu bloklanır" iddiasının bu şeritte
de gösterilebilmesi gerekiyor. Kontrolün kendisinin doğruluğu Şerit 2'nin testidir
(T016); burada test edilen, bu şeridin BLOKLAMAYA UYMASI — bloklanan metnin kullanıcıya
sızmaması ve yerine kaynaklı şablona düşülmesi.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.api.chat import (
    MESSAGE_BLOCKED,
    MESSAGE_INSUFFICIENT_CONTEXT,
    produce_answer,
)
from app.contracts import (
    AnswerStatus,
    ChatMode,
    Citation,
    GeneratedAnswer,
    GuardrailVerdict,
    RetrievedChunk,
    SocraticStage,
)
from app.core.config import Settings
from app.modules.assessment import socratic
from app.modules.assessment.socratic import (
    AttemptKind,
    SocraticState,
    advance,
    classify_attempt,
)

COURSE_ID = UUID("11111111-1111-1111-1111-111111111111")

# Sızıntı ihtimali olan bir "cevap": testlerin hiçbirinde kullanıcıya ULAŞMAMALI.
LEAKED_SOLUTION = "İşte tam çözüm: cevap 42, kod ```while True: pass```"


def make_chunk(
    *,
    text: str = "Deadlock için dört koşulun aynı anda sağlanması gerekir.",
    dense_score: float = 0.82,
    file_name: str = "isletim-sistemleri-hafta3.pdf",
    page_number: int | None = 7,
    section_title: str | None = "Deadlock Koşulları",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name=file_name,
        page_number=page_number,
        slide_number=None,
        section_title=section_title,
        text=text,
        dense_score=dense_score,
        fts_score=0.4,
        # Gerçekçi RRF değeri: eşik füzyon skoruna baksaydı her soru reddedilirdi.
        fused_score=0.032,
    )


class FakeRetriever:
    """`contracts.Retriever` protokolü."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.calls = 0

    async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]:
        self.calls += 1
        del course_id, query
        return self._chunks[:limit]


class FakeGenerator:
    """`contracts.Generator` protokolü. Her çağrıda sıradaki hazır cevabı döner."""

    def __init__(self, answers: list[GeneratedAnswer]) -> None:
        self._answers = answers
        self.calls = 0
        self.seen_stages: list[SocraticStage | None] = []
        #: Uç, öğrencinin denemesini gerçekten geçiriyor mu? Kaydedilmezse
        #: "ipucu denemeye göre şekilleniyor" iddiası test edilemez (Anayasa III).
        self.seen_attempts: list[str | None] = []

    async def generate(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        student_attempt: str | None = None,
    ) -> GeneratedAnswer:
        del question, chunks, mode
        self.calls += 1
        self.seen_stages.append(socratic_stage)
        self.seen_attempts.append(student_attempt)
        index = min(self.calls - 1, len(self._answers) - 1)
        answer = self._answers[index]
        # Üretim katmanı her çağrıda yeni nesne döndürür; zincir mutasyonu testler
        # arasında sızmasın diye kopyalanıyor.
        return GeneratedAnswer(
            status=answer.status,
            mode=answer.mode,
            text=answer.text,
            citations=list(answer.citations),
            socratic_stage=answer.socratic_stage,
        )


class CitationGuardrail:
    """Set-membership: cevaptaki her chunk_id retrieve edilen kümede olmalı."""

    def check(self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]) -> GuardrailVerdict:
        allowed = {chunk.chunk_id for chunk in retrieved}
        dropped = [c.chunk_id for c in answer.citations if c.chunk_id not in allowed]
        remaining = [c for c in answer.citations if c.chunk_id in allowed]
        if not remaining:
            return GuardrailVerdict(
                blocked=True, reason="citation:no_valid_citation", dropped_citations=dropped
            )
        return GuardrailVerdict(blocked=False, dropped_citations=dropped)


class AlwaysBlockingGuardrail:
    """Pedagojik filtreyi temsil eder: metni her koşulda reddeder."""

    def __init__(self) -> None:
        self.calls = 0

    def check(self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]) -> GuardrailVerdict:
        del answer, retrieved
        self.calls += 1
        return GuardrailVerdict(blocked=True, reason="leakage:code_fence")


def settings() -> Settings:
    """Ortamdan bağımsız ayar: bu dosya .env'e ve veritabanına bağlı değil."""
    return Settings(dev_auth_enabled=True, evidence_threshold=0.35, retrieval_top_k=8)


async def run_turn(
    *,
    message: str,
    chunks: list[RetrievedChunk],
    generator: FakeGenerator,
    guardrails: list[object],
    state: SocraticState | None,
) -> tuple[GeneratedAnswer, socratic.SocraticDecision]:
    decision = advance(state, message)
    outcome = await produce_answer(
        question=message,
        course_id=COURSE_ID,
        mode=ChatMode.SOCRATIC,
        decision=decision,
        retriever=FakeRetriever(chunks),
        generator=generator,
        guardrails=guardrails,  # type: ignore[arg-type]
        settings=settings(),
    )
    return outcome.answer, decision


# ---------------------------------------------------------------------------
# Vaka 1 — ilk turda cevap verilmez
# ---------------------------------------------------------------------------


class TestIlkTur:
    def test_ilk_tur_tani_kademesinde_baslar(self) -> None:
        decision = advance(None, "Deadlock nedir?")

        assert decision.stage is SocraticStage.DIAGNOSE
        assert decision.advanced is False
        assert decision.state.attempts == 0

    async def test_model_kendini_ust_kademeye_terfi_ettiremez(self) -> None:
        """Kademe sunucu otoritesindedir.

        Üretim katmanı "ben kaynaklı açıklama üretiyorum" dese bile servis edilen
        kademe state machine'in kararıdır. Aksi hâlde merdiven, modelin ikna
        edilebilirliği kadar sağlam olurdu.
        """
        chunk = make_chunk()
        generator = FakeGenerator(
            [
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=ChatMode.SOCRATIC,
                    text="Kavramı birlikte açalım.",
                    citations=[Citation(chunk.chunk_id, chunk.file_name, chunk.location, "…")],
                    socratic_stage=SocraticStage.EXPLAIN_WITH_SOURCE,
                )
            ]
        )

        answer, _ = await run_turn(
            message="Deadlock nedir?",
            chunks=[chunk],
            generator=generator,
            guardrails=[CitationGuardrail()],
            state=None,
        )

        assert answer.socratic_stage is SocraticStage.DIAGNOSE
        assert generator.seen_stages == [SocraticStage.DIAGNOSE]


# ---------------------------------------------------------------------------
# Vaka 2 — deneme olmadan kademe atlanmaz
# ---------------------------------------------------------------------------


class TestKademeIlerlemesi:
    @pytest.mark.parametrize(
        "message",
        [
            "sadece söyle",
            "Sadece Söyle",
            "cevabı ver",
            "bana cevabı yaz",
            "çözümü göster",
            "direkt cevap istiyorum",
            "just tell me",
        ],
    )
    def test_cevap_dayatmasi_ilerletmez(self, message: str) -> None:
        state = SocraticState(stage=SocraticStage.DIAGNOSE)

        decision = advance(state, message)

        assert decision.attempt_kind is AttemptKind.ANSWER_DEMAND
        assert decision.stage is SocraticStage.DIAGNOSE
        assert decision.advanced is False
        assert decision.refusal_notice is not None
        assert decision.state.refusals == 1

    def test_bos_mesaj_ilerletmez(self) -> None:
        decision = advance(SocraticState(stage=SocraticStage.NUDGE), "   ")

        assert decision.attempt_kind is AttemptKind.EMPTY
        assert decision.stage is SocraticStage.NUDGE
        assert decision.advanced is False

    def test_bilmiyorum_yalniz_tani_kademesinde_ilerletir(self) -> None:
        """Kararın kendisi: gerekçesi socratic.py modül docstring'inde."""
        ilk = advance(SocraticState(stage=SocraticStage.DIAGNOSE), "bilmiyorum")
        sonraki = advance(SocraticState(stage=SocraticStage.NUDGE), "bilmiyorum")

        assert ilk.advanced is True
        assert ilk.stage is SocraticStage.NUDGE
        assert sonraki.advanced is False
        assert sonraki.stage is SocraticStage.NUDGE
        assert sonraki.refusal_notice is not None

    def test_tereddutlu_ama_denenmis_cevap_ilerletir(self) -> None:
        """«bilmiyorum ama sanırım …» bir denemedir; tereddüt cezalandırılmaz."""
        decision = advance(
            SocraticState(stage=SocraticStage.NUDGE),
            "bilmiyorum ama sanırım dört koşulun hepsi aynı anda sağlanmalı",
        )

        assert decision.attempt_kind is AttemptKind.SUBSTANTIVE
        assert decision.stage is SocraticStage.CONCEPT_HINT

    def test_yanlis_cevap_da_ilerletir(self) -> None:
        decision = advance(SocraticState(stage=SocraticStage.DIAGNOSE), "sanırım iki koşul var")

        assert decision.attempt_kind is AttemptKind.SUBSTANTIVE
        assert decision.advanced is True

    def test_merdiven_sonuna_kadar_cikar_ve_orada_kalir(self) -> None:
        state = SocraticState()
        for beklenen in socratic.STAGE_ORDER[1:]:
            decision = advance(state, "denemem: dört koşul sağlanıyor olabilir")
            state = decision.state
            assert decision.stage is beklenen

        son = advance(state, "yeni bir denemem daha var")

        assert son.stage is SocraticStage.EXPLAIN_WITH_SOURCE
        assert son.advanced is False
        assert son.state.attempts == 5

    def test_her_gecis_olay_olarak_kaydedilir(self) -> None:
        """FR-014: «sistem gerçekten yönlendirdi mi» sonradan cevaplanabilmeli."""
        state = SocraticState()
        for _ in range(3):
            state = advance(state, "denemem şu: dört koşul").state

        assert [(t.from_stage, t.to_stage) for t in state.transitions] == [
            (SocraticStage.DIAGNOSE, SocraticStage.NUDGE),
            (SocraticStage.NUDGE, SocraticStage.CONCEPT_HINT),
            (SocraticStage.CONCEPT_HINT, SocraticStage.SIMILAR_EXAMPLE),
        ]


class TestDenemeSiniflandirmasi:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("", AttemptKind.EMPTY),
            ("   \n ", AttemptKind.EMPTY),
            ("?", AttemptKind.UNSURE),
            ("hı", AttemptKind.UNSURE),
            ("bilmiyorum", AttemptKind.UNSURE),
            ("BİLMİYORUM", AttemptKind.UNSURE),
            ("hiçbir fikrim yok", AttemptKind.UNSURE),
            ("no idea", AttemptKind.UNSURE),
            ("deadlock", AttemptKind.SUBSTANTIVE),
            ("bence kaynak beklemesi yüzünden", AttemptKind.SUBSTANTIVE),
        ],
    )
    def test_siniflandirma(self, message: str, expected: AttemptKind) -> None:
        assert classify_attempt(message) is expected

    def test_turkce_buyuk_harf_tuzagi(self) -> None:
        """«I» ve «İ» ayrımı: naif lower() bu iki mesajı farklı sınıflara düşürürdü."""
        assert classify_attempt("SADECE SÖYLE") is AttemptKind.ANSWER_DEMAND
        assert classify_attempt("sadece soyle") is AttemptKind.ANSWER_DEMAND


# ---------------------------------------------------------------------------
# Vaka 3 — kaynaksız ipucu bloklanır
# ---------------------------------------------------------------------------


class TestKaynaksizIpucu:
    async def test_uydurma_atifli_ipucu_kullaniciya_gitmez(self) -> None:
        """Model retrieve EDİLMEMİŞ bir kaynağa atıf yaparsa metni gösterilmez."""
        chunk = make_chunk()
        uydurma = Citation(uuid4(), "olmayan-dosya.pdf", "Sayfa 99", "uydurma alıntı")
        generator = FakeGenerator(
            [
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=ChatMode.SOCRATIC,
                    text=LEAKED_SOLUTION,
                    citations=[uydurma],
                )
            ]
        )

        answer, _ = await run_turn(
            message="denemem: dört koşul",
            chunks=[chunk],
            generator=generator,
            guardrails=[CitationGuardrail()],
            state=SocraticState(stage=SocraticStage.DIAGNOSE),
        )

        assert LEAKED_SOLUTION not in answer.text
        assert answer.citations
        assert all(c.chunk_id == chunk.chunk_id for c in answer.citations)

    async def test_kaynak_yoksa_ipucu_da_yok(self) -> None:
        """FR-016: her ipucu bir kaynak parçadan türer. Parça yoksa ipucu da yok."""
        generator = FakeGenerator([])

        answer, _ = await run_turn(
            message="denemem: dört koşul",
            chunks=[],
            generator=generator,
            guardrails=[CitationGuardrail()],
            state=SocraticState(stage=SocraticStage.DIAGNOSE),
        )

        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT
        assert answer.text == MESSAGE_INSUFFICIENT_CONTEXT
        assert answer.citations == []
        # Kanıt yoksa LLM'e hiç gidilmez.
        assert generator.calls == 0

    async def test_esik_alti_kanit_llm_cagirmaz(self) -> None:
        zayif = make_chunk(dense_score=0.10)
        generator = FakeGenerator([])

        answer, _ = await run_turn(
            message="denemem: dört koşul",
            chunks=[zayif],
            generator=generator,
            guardrails=[CitationGuardrail()],
            state=SocraticState(stage=SocraticStage.DIAGNOSE),
        )

        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT
        assert generator.calls == 0

    async def test_qa_modunda_bloklanan_cevap_gosterilmez(self) -> None:
        """QA'da deterministik son durak yoktur: gösterilemeyen cevap gösterilmez."""
        chunk = make_chunk()
        generator = FakeGenerator(
            [
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=ChatMode.QA,
                    text=LEAKED_SOLUTION,
                    citations=[Citation(uuid4(), "yok.pdf", "Sayfa 1", "…")],
                )
            ]
        )

        answer = (
            await produce_answer(
                question="Deadlock nedir?",
                course_id=COURSE_ID,
                mode=ChatMode.QA,
                decision=None,
                retriever=FakeRetriever([chunk]),
                generator=generator,
                guardrails=[CitationGuardrail()],  # type: ignore[list-item]
                settings=settings(),
            )
        ).answer

        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT
        assert answer.text == MESSAGE_BLOCKED
        assert LEAKED_SOLUTION not in answer.text
        # QA modunda yeniden üretim yoktur: tek çağrı.
        assert generator.calls == 1


# ---------------------------------------------------------------------------
# Vaka 4 — ısrarcı öğrenci şablon ipucuna düşer
# ---------------------------------------------------------------------------


class TestIsrarciOgrenci:
    async def test_cevap_dayatmasi_sablona_duser_ve_llm_harcamaz(self) -> None:
        """Israr üretim çağırmaz: merdiven ilerlemez, bütçe de tükenmez."""
        chunk = make_chunk()
        generator = FakeGenerator([])
        state = SocraticState(stage=SocraticStage.NUDGE)

        answer, decision = await run_turn(
            message="uğraşmak istemiyorum, sadece söyle",
            chunks=[chunk],
            generator=generator,
            guardrails=[CitationGuardrail()],
            state=state,
        )

        assert generator.calls == 0
        assert decision.stage is SocraticStage.NUDGE
        assert answer.status is AnswerStatus.ANSWERED
        assert answer.socratic_stage is SocraticStage.NUDGE
        assert [c.chunk_id for c in answer.citations] == [chunk.chunk_id]
        # Şablon, chunk metnini alıntılamaz; yalnız kaynağı işaret eder.
        assert chunk.text not in answer.text
        assert chunk.file_name in answer.text

    async def test_filtre_israrla_ihlal_ederse_bir_regen_sonra_sablon(self) -> None:
        """FR-015: ihlalde bir kez yeniden üret, sürerse deterministik şablona düş."""
        chunk = make_chunk()
        filtre = AlwaysBlockingGuardrail()
        generator = FakeGenerator(
            [
                GeneratedAnswer(
                    status=AnswerStatus.ANSWERED,
                    mode=ChatMode.SOCRATIC,
                    text=LEAKED_SOLUTION,
                    citations=[Citation(chunk.chunk_id, chunk.file_name, chunk.location, "…")],
                )
            ]
        )

        answer, _ = await run_turn(
            message="denemem: dört koşul sağlanıyor",
            chunks=[chunk],
            generator=generator,
            guardrails=[filtre],
            state=SocraticState(stage=SocraticStage.CONCEPT_HINT),
        )

        assert generator.calls == 2, "tam olarak bir kez yeniden üretilmeli"
        assert LEAKED_SOLUTION not in answer.text
        assert answer.status is AnswerStatus.ANSWERED
        assert answer.socratic_stage is SocraticStage.SIMILAR_EXAMPLE
        assert [c.chunk_id for c in answer.citations] == [chunk.chunk_id]

    def test_sablon_ipuclari_hicbir_kademede_chunk_metnini_alintilamaz(self) -> None:
        """SC-007'nin şablon ayağı: son durak yapısal olarak sızdıramaz."""
        chunk = make_chunk(text=LEAKED_SOLUTION)

        for stage in socratic.STAGE_ORDER:
            text, citation = socratic.template_hint(stage, chunk)

            assert LEAKED_SOLUTION not in text
            assert citation.chunk_id == chunk.chunk_id
            assert chunk.file_name in text


# ---------------------------------------------------------------------------
# Vaka 5 — durum kalıcıdır
# ---------------------------------------------------------------------------


class TestDurumKaliciligi:
    def test_json_gidis_donusu_kademeyi_korur(self) -> None:
        state = SocraticState()
        for _ in range(2):
            state = advance(state, "denemem: dört koşul").state

        geri = SocraticState.from_json(state.to_json())

        assert geri.stage is state.stage
        assert geri.attempts == state.attempts
        assert geri.refusals == state.refusals
        assert [(t.from_stage, t.to_stage) for t in geri.transitions] == [
            (t.from_stage, t.to_stage) for t in state.transitions
        ]

    def test_oturum_yeniden_yuklendiginde_merdiven_kaldigi_yerden_devam_eder(self) -> None:
        state = advance(SocraticState(), "denemem: dört koşul").state
        yeniden_yuklenen = SocraticState.from_json(state.to_json())

        devam = advance(yeniden_yuklenen, "ikinci denemem: birinci koşul sağlanmıyor")

        assert devam.stage is SocraticStage.CONCEPT_HINT

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            {},
            "bozuk",
            {"stage": "uydurma_kademe"},
        ],
    )
    def test_okunamayan_durum_merdivenin_basina_duser(self, raw: object) -> None:
        """Fail-closed: kademe okunamıyorsa sona değil, başa dönülür."""
        state = SocraticState.from_json(raw)

        assert state.stage is SocraticStage.DIAGNOSE
        assert state.attempts >= 0

    def test_kademe_gecerliyken_bozuk_yan_alanlar_kademeyi_dusurmez(self) -> None:
        """Onarım en az yıkıcı olandır: okunabilen alan korunur, gerisi temizlenir.

        Bozuk bir sayaç yüzünden öğrenciyi merdivenin başına atmak, onu kendi
        yapmadığı bir hata için cezalandırmak olurdu.
        """
        state = SocraticState.from_json(
            {"stage": "nudge", "attempts": -5, "transitions": "liste değil"}
        )

        assert state.stage is SocraticStage.NUDGE
        assert state.attempts == 0
        assert state.transitions == ()

    def test_bozuk_gecis_kaydi_tum_gecmisi_dusurmez(self) -> None:
        raw = {
            "stage": "concept_hint",
            "attempts": 2,
            "refusals": 0,
            "transitions": [
                {"from": "diagnose", "to": "nudge", "attempt": "substantive"},
                {"from": "yok", "to": "olmayan", "attempt": "?"},
            ],
        }

        state = SocraticState.from_json(raw)

        assert state.stage is SocraticStage.CONCEPT_HINT
        assert len(state.transitions) == 1

    def test_gecis_gecmisi_sinirsiz_buyumez(self) -> None:
        state = SocraticState()
        for _ in range(socratic.MAX_TRANSITIONS_KEPT + 20):
            state = advance(state, "yeni bir denemem").state

        assert len(state.transitions) <= socratic.MAX_TRANSITIONS_KEPT
