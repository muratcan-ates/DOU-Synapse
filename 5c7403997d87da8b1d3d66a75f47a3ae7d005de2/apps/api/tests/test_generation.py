"""Üretim katmanı testleri — LLM erişimi, failover, şema kapısı (T009/T012/T016).

Hiçbir test ağa çıkmaz. Sağlayıcı davranışı `completion_fn` enjeksiyonuyla
taklit edilir; sahte sağlayıcı zaten deterministiktir. Bu bir kolaylık değil
zorunluluk: ağa bağımlı bir test kırmızı yandığında koddaki hata hakkında
hiçbir şey söylemez, yalnız o an internetin durumunu raporlar.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.contracts import AnswerStatus, ChatMode, RetrievedChunk, SocraticStage
from app.core.config import Settings
from app.modules.generation.fake import FAKE_PROVIDER, FakeLlmClient, parse_sources
from app.modules.generation.llm import (
    LiteLlmClient,
    LlmRequest,
    LlmUnavailableError,
    build_llm_client,
    provider_of,
)
from app.modules.generation.service import USER_TEXT, GenerationService
from app.modules.guardrails.chain import AnswerPipeline
from app.schemas.chat import ChatRequest, to_chat_response


def chunk(
    text: str = "Kilitlenme, her biri diğerinin kaynağını bekleyen süreçlerin durumudur.",
    *,
    file_name: str = "OS-Hafta3.pdf",
    page_number: int | None = 7,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name=file_name,
        page_number=page_number,
        slide_number=None,
        section_title=None,
        text=text,
        fused_score=0.9,
    )


def settings_for(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "dev_auth_enabled": True,
        "llm_primary_model": "groq/llama-3.3-70b-versatile",
        "llm_fallback_model": "gemini/gemini-2.0-flash",
        # Sağlayıcı önekiyle başlamayan değerler bilinçli: gerçek anahtar
        # biçimini taklit eden bir test sabiti, sızıntı taramalarında
        # kalıcı yanlış pozitif üretir.
        "groq_api_key": "test-groq-anahtari",
        "gemini_api_key": "test-gemini-anahtari",
        "llm_max_retries": 0,
    }
    base.update(overrides)
    return Settings(**base)


class ProviderError(Exception):
    """LiteLLM istisnalarının şeklini taklit eder: adı ve status_code'u vardır."""

    def __init__(self, status_code: int, name: str = "RateLimitError") -> None:
        super().__init__(f"{name}: {status_code}")
        self.status_code = status_code
        self.__class__.__name__ = name


def ok_response(content: str = '{"status": "answered", "answer": "tamam"}') -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 40},
    }


class RecordingCompletion:
    """Model adına göre davranan sahte `litellm.acompletion`."""

    def __init__(self, *, failing_prefixes: tuple[str, ...], status_code: int = 429) -> None:
        self._failing = failing_prefixes
        self._status = status_code
        self.models: list[str] = []

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        model = kwargs["model"]
        self.models.append(model)
        if model.startswith(self._failing):
            raise ProviderError(self._status)
        return ok_response()


@contextmanager
def network_blocked() -> Iterator[None]:
    """Testin gövdesi boyunca giden TCP bağlantılarını yasaklar.

    "Ağsız koşuyor" iddiasını gerçekten sınamanın tek yolu ağı kesmek; sağlayıcı
    adına bakan bir test, sessizce ağa çıkan bir kod yolunu yakalayamaz.
    """
    original = socket.socket.connect

    def _refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("bu yolda ağ erişimi olmamalıydı")

    socket.socket.connect = _refuse  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = original  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# T009 — failover ve dayanıklılık
# ---------------------------------------------------------------------------


class TestFailover:
    async def test_groq_429_donunca_gemini_devralir(self) -> None:
        """Kota dolduğunda sistem elle müdahale beklemeden ikinciye düşer."""
        completion = RecordingCompletion(failing_prefixes=("groq/",))
        client = LiteLlmClient(settings_for(), completion_fn=completion)

        result = await client.complete(LlmRequest(system="s", user="u"))

        assert result.provider == "gemini"
        assert completion.models == [
            "groq/llama-3.3-70b-versatile",
            "gemini/gemini-2.0-flash",
        ]

    async def test_kimlik_hatasinda_tekrar_denenmez(self) -> None:
        """401 kalıcı bir hata: aynı sağlayıcıda retry kotayı ve süreyi boşa harcar."""
        completion = RecordingCompletion(failing_prefixes=("groq/",), status_code=401)
        client = LiteLlmClient(settings_for(llm_max_retries=3), completion_fn=completion)

        result = await client.complete(LlmRequest(system="s", user="u"))

        assert result.provider == "gemini"
        assert completion.models.count("groq/llama-3.3-70b-versatile") == 1

    async def test_gecici_hatada_ayni_saglayici_tekrar_denenir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(asyncio, "sleep", _no_sleep)
        completion = RecordingCompletion(failing_prefixes=("groq/",), status_code=503)
        client = LiteLlmClient(settings_for(llm_max_retries=2), completion_fn=completion)

        await client.complete(LlmRequest(system="s", user="u"))

        # llm_max_retries=2 → ilk deneme + iki tekrar = 3, sonra failover.
        assert completion.models.count("groq/llama-3.3-70b-versatile") == 3

    async def test_tum_saglayicilar_dustugunde_hata_yukselir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Abstention DÖNÜLMEZ: servis arızası "materyalde kanıt yok" değildir."""
        monkeypatch.setattr(asyncio, "sleep", _no_sleep)
        completion = RecordingCompletion(failing_prefixes=("groq/", "gemini/"))
        client = LiteLlmClient(settings_for(llm_max_retries=1), completion_fn=completion)

        with pytest.raises(LlmUnavailableError):
            await client.complete(LlmRequest(system="s", user="u"))

    async def test_ayni_model_iki_kez_denenmez(self) -> None:
        completion = RecordingCompletion(failing_prefixes=())
        client = LiteLlmClient(
            settings_for(llm_primary_model="groq/x", llm_fallback_model="groq/x"),
            completion_fn=completion,
        )

        await client.complete(LlmRequest(system="s", user="u"))

        assert completion.models == ["groq/x"]

    def test_saglayici_adi_model_adindan_turer(self) -> None:
        assert provider_of("groq/llama-3.3-70b-versatile") == "groq"
        assert provider_of("gemini/gemini-2.0-flash") == "gemini"


async def _no_sleep(_seconds: float) -> None:
    return None


class TestSaglayiciSecimi:
    def test_anahtar_yoksa_sahte_saglayiciya_dusulur(self) -> None:
        client = build_llm_client(settings_for(groq_api_key=None, gemini_api_key=None))
        assert isinstance(client, FakeLlmClient)

    def test_bayrak_aciksa_anahtar_olsa_bile_sahte_kullanilir(self) -> None:
        client = build_llm_client(settings_for(llm_fake_provider=True))
        assert isinstance(client, FakeLlmClient)

    def test_anahtar_varsa_gercek_istemci_kurulur(self) -> None:
        assert isinstance(build_llm_client(settings_for()), LiteLlmClient)

    def test_uretimde_sahte_saglayici_ayarlari_reddedilir(self) -> None:
        """Üretimde sahte cevap gerçek öğrenciye gider ve fark etmenin yolu yoktur."""
        with pytest.raises(ValueError, match="LLM_FAKE_PROVIDER"):
            Settings(
                environment="production",
                supabase_jwt_secret="x",
                dev_auth_enabled=False,
                llm_fake_provider=True,
            )


# ---------------------------------------------------------------------------
# Sahte sağlayıcı — çevrimdışı demo sigortası
# ---------------------------------------------------------------------------


class TestSahteSaglayici:
    async def test_agsiz_kosar(self) -> None:
        """PLAN plan C: internetsiz sunum bu yola dayanıyor."""
        kaynak = chunk()
        pipeline = AnswerPipeline(GenerationService(llm=FakeLlmClient()))

        with network_blocked():
            result = await pipeline.run(
                question="Kilitlenme nedir?", chunks=[kaynak], mode=ChatMode.QA
            )

        assert not result.blocked
        assert result.answer.provider == FAKE_PROVIDER

    async def test_ayni_girdi_ayni_cevabi_uretir(self) -> None:
        """Deterministiklik: çevrimdışı demo prova edilebilir olmalı."""
        kaynak = chunk()
        service = GenerationService(llm=FakeLlmClient())

        birinci = await service.generate(question="Nedir?", chunks=[kaynak], mode=ChatMode.QA)
        ikinci = await service.generate(question="Nedir?", chunks=[kaynak], mode=ChatMode.QA)

        assert birinci.text == ikinci.text
        assert [c.chunk_id for c in birinci.citations] == [c.chunk_id for c in ikinci.citations]

    async def test_yalnizca_verilen_chunklara_atif_yapar(self) -> None:
        """Sahte sağlayıcı bir stub olsaydı guardrail testleri kendi sahnesini doğrulardı."""
        kaynaklar = [chunk(), chunk(file_name="OS-Hafta4.pdf", page_number=12)]
        service = GenerationService(llm=FakeLlmClient())

        answer = await service.generate(question="Nedir?", chunks=kaynaklar, mode=ChatMode.QA)

        verilen = {k.chunk_id for k in kaynaklar}
        assert {c.chunk_id for c in answer.citations} <= verilen
        assert answer.citations, "en az bir gerçek atıf üretmeli"

    def test_prompt_ayristirmasi_kacisi_dogrular(self) -> None:
        """Ayrıştırıcı, kaçış mekanizmasının canlı kontrolü."""
        from app.modules.generation.prompts import build_context_block

        kaynak = chunk("İçinde <source id='sahte'> geçen materyal")
        okunan = parse_sources(build_context_block([kaynak]))

        assert len(okunan) == 1
        assert okunan[0].chunk_id == str(kaynak.chunk_id)

    async def test_sokratik_modda_cozum_vermez(self) -> None:
        from app.modules.guardrails import leakage

        for stage in SocraticStage:
            service = GenerationService(llm=FakeLlmClient())
            answer = await service.generate(
                question="Nasıl çözerim?",
                chunks=[chunk()],
                mode=ChatMode.SOCRATIC,
                socratic_stage=stage,
            )
            assert leakage.detect(answer.text) == [], f"{stage} kademesi sızdırdı"


# ---------------------------------------------------------------------------
# T012 — şema kapısı ve fail-closed davranış
# ---------------------------------------------------------------------------


class ScriptedLlm:
    def __init__(self, *payloads: str) -> None:
        self._payloads = payloads or ("",)
        self.calls = 0

    async def complete(self, request: LlmRequest) -> Any:
        from app.modules.generation.llm import LlmCompletion

        index = min(self.calls, len(self._payloads) - 1)
        self.calls += 1
        return LlmCompletion(text=self._payloads[index], provider="scripted", model="scripted/test")


class TestUretimServisi:
    async def test_chunk_yoksa_llm_hic_cagrilmaz(self) -> None:
        """Kanıt yokken model çağırmak, boşluğu doldurmasını istemektir."""
        llm = ScriptedLlm('{"status": "answered", "answer": "uydurma"}')
        service = GenerationService(llm=llm)

        answer = await service.generate(question="Nedir?", chunks=[], mode=ChatMode.QA)

        assert llm.calls == 0
        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT
        assert answer.citations == []

    async def test_bozuk_cikti_bir_kez_yeniden_denenir(self) -> None:
        llm = ScriptedLlm(
            "Tabii, işte cevap!",  # JSON değil
            '{"status": "answered", "answer": "Materyale göre budur.", "citations": []}',
        )
        service = GenerationService(llm=llm, settings=settings_for(llm_max_retries=1))

        answer = await service.generate(question="Nedir?", chunks=[chunk()], mode=ChatMode.QA)

        assert llm.calls == 2
        assert answer.text == "Materyale göre budur."

    async def test_israrla_bozuk_cikti_abstentiona_duser(self) -> None:
        llm = ScriptedLlm("hiç JSON yok")
        service = GenerationService(llm=llm, settings=settings_for(llm_max_retries=1))

        answer = await service.generate(question="Nedir?", chunks=[chunk()], mode=ChatMode.QA)

        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT
        assert answer.text == USER_TEXT["insufficient_context"]

    async def test_kod_citine_alinmis_json_kabul_edilir(self) -> None:
        """Modeller JSON'u çite alma eğiliminde; bu gereksiz retry üretiyordu."""
        llm = ScriptedLlm('İşte:\n```json\n{"status": "answered", "answer": "Budur."}\n```')
        service = GenerationService(llm=llm)

        answer = await service.generate(question="Nedir?", chunks=[chunk()], mode=ChatMode.QA)

        assert llm.calls == 1
        assert answer.text == "Budur."

    async def test_answered_ama_bos_metin_abstentiona_cevrilir(self) -> None:
        llm = ScriptedLlm('{"status": "answered", "answer": "   ", "citations": []}')
        service = GenerationService(llm=llm, settings=settings_for(llm_max_retries=0))

        answer = await service.generate(question="Nedir?", chunks=[chunk()], mode=ChatMode.QA)

        assert answer.status is AnswerStatus.INSUFFICIENT_CONTEXT

    async def test_saglayici_ve_model_cevapta_tasinir(self) -> None:
        """Hangi cevabın neyle üretildiği raporlanabilmeli (Anayasa III)."""
        service = GenerationService(llm=FakeLlmClient())

        answer = await service.generate(question="Nedir?", chunks=[chunk()], mode=ChatMode.QA)

        assert answer.provider == FAKE_PROVIDER
        assert answer.model


# ---------------------------------------------------------------------------
# Uçtan uca — sahte retrieval üzerinde
# ---------------------------------------------------------------------------


class TestUctanUca:
    async def test_kaynakli_cevap_zarfa_kadar_gider(self) -> None:
        kaynak = chunk(file_name="OS-Hafta3.pdf", page_number=7)
        pipeline = AnswerPipeline(GenerationService(llm=FakeLlmClient()))

        result = await pipeline.run(question="Kilitlenme nedir?", chunks=[kaynak], mode=ChatMode.QA)
        response = to_chat_response(
            result.answer, session_id=uuid4(), message_id=uuid4(), claims=result.claims
        )

        assert response.status is AnswerStatus.ANSWERED
        assert len(response.citations) == 1
        assert response.citations[0].file_name == "OS-Hafta3.pdf"
        assert response.citations[0].location == "Sayfa 7"
        assert response.citations[0].snippet
        assert response.hints == [], "soru-cevap modunda ipucu üretilmez"

    async def test_sokratik_cevap_ipucu_olarak_da_sunulur(self) -> None:
        kaynak = chunk()
        pipeline = AnswerPipeline(GenerationService(llm=FakeLlmClient()))

        result = await pipeline.run(
            question="Nasıl çözerim?",
            chunks=[kaynak],
            mode=ChatMode.SOCRATIC,
            socratic_stage=SocraticStage.CONCEPT_HINT,
        )
        response = to_chat_response(
            result.answer, session_id=uuid4(), message_id=uuid4(), claims=result.claims
        )

        assert len(response.hints) == 1
        assert response.hints[0].chunk_id == kaynak.chunk_id
        assert response.hints[0].stage is SocraticStage.CONCEPT_HINT

    def test_slayt_konumu_da_desteklenir(self) -> None:
        from app.schemas.chat import snippet_of

        slayt = RetrievedChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            file_name="Sunum.pptx",
            page_number=None,
            slide_number=3,
            section_title=None,
            text="Kilitlenme koşulları",
        )
        assert slayt.location == "Slayt 3"
        assert snippet_of(slayt) == "Kilitlenme koşulları"


class TestIstekSemasi:
    def test_asiri_uzun_soru_reddedilir(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(question="a" * 5000)

    def test_istemci_kademe_secemez(self) -> None:
        """Kademeyi istemci seçebilseydi öğrenci merdiveni atlardı (FR-014)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest(question="Nedir?", socratic_stage="explain_with_source")

    def test_varsayilan_mod_soru_cevap(self) -> None:
        assert ChatRequest(question="Nedir?").mode is ChatMode.QA

    def test_oturum_kimligi_opsiyonel(self) -> None:
        oturum = uuid4()
        assert ChatRequest(question="Nedir?", session_id=oturum).session_id == oturum
        assert ChatRequest(question="Nedir?").session_id is None


def test_uuid_tipleri_zarfa_kadar_korunur() -> None:
    """chunk_id string'e düşerse set-membership sessizce yanlış çalışır."""
    kaynak = chunk()
    assert isinstance(kaynak.chunk_id, UUID)
