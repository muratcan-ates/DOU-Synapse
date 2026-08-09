"""Değerlendirme metriklerinin tanımlarını sabitleyen testler (T042).

Neden API test paketinin içinde: bu fonksiyonlar `evaluation/` altında yaşıyor ama
raporun her sayısını üretiyorlar ve tanım belirsizliği jürinin ilk saldırı noktası.
Buraya konunca CI her koşuda tanımları doğruluyor; `evaluation/` altında dursalardı
hiçbir otomatik koşu onlara dokunmazdı.

Her test bir TANIMI sabitler, bir uygulamayı değil. "Recall@5 neydi?" sorusunun
cevabı burada koşan koddur.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVALUATION_ROOT = Path(__file__).resolve().parents[3] / "evaluation"
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

import evaluate  # noqa: E402
import goldset  # noqa: E402
import metrics  # noqa: E402


def _outcome(
    item_id: str, ranks: tuple[tuple[int, ...], ...], category: str = "direct"
) -> metrics.RetrievalOutcome:
    return metrics.RetrievalOutcome(
        item_id=item_id, category=category, ranks_by_source=ranks, retrieved_count=8
    )


class TestRecall:
    def test_recall_en_az_bir_kaynak_yeter(self) -> None:
        """Recall@k tanımı: beklenen kaynaklardan EN AZ BİRİ ilk k'de."""
        outcomes = [
            _outcome("A", ((3,), (7,))),  # ilk isabet 3 -> @5 var
            _outcome("B", ((6,),)),  # ilk isabet 6 -> @5 yok, @8 var
            _outcome("C", ((), ())),  # hiç isabet yok
        ]
        assert metrics.recall_at_k(outcomes, 5) == pytest.approx(1 / 3)
        assert metrics.recall_at_k(outcomes, 8) == pytest.approx(2 / 3)

    def test_tam_kapsama_butun_kaynaklari_ister(self) -> None:
        """Tam kapsama, Recall'dan FARKLI bir sayıdır ve ayrı raporlanır."""
        outcomes = [
            _outcome("A", ((1,), (2,))),  # ikisi de ilk 5'te
            _outcome("B", ((1,), (7,))),  # biri 7'de -> @5 tam değil, @8 tam
        ]
        assert metrics.recall_at_k(outcomes, 5) == pytest.approx(1.0)
        assert metrics.full_coverage_at_k(outcomes, 5) == pytest.approx(0.5)
        assert metrics.full_coverage_at_k(outcomes, 8) == pytest.approx(1.0)

    def test_tam_kapsama_yalniz_cok_kaynakli_sorularda_hesaplanir(self) -> None:
        """Tek kaynaklı soruda tam kapsama Recall'ın aynısıdır; oranı şişirirdi."""
        outcomes = [_outcome("A", ((1,),)), _outcome("B", ((1,), (9,)))]
        assert metrics.full_coverage_at_k(outcomes, 5) == pytest.approx(0.0)

    def test_bos_kumede_metrik_sifir_degil_none(self) -> None:
        """Ölçülmemiş bir şey 0.0 diye raporlanamaz (Anayasa III)."""
        assert metrics.recall_at_k([], 5) is None
        assert metrics.mean_reciprocal_rank([]) is None


class TestMrr:
    def test_ilk_ilgili_sonucun_tersi(self) -> None:
        outcomes = [_outcome("A", ((1,),)), _outcome("B", ((4,),)), _outcome("C", ((),))]
        assert metrics.mean_reciprocal_rank(outcomes) == pytest.approx((1.0 + 0.25 + 0.0) / 3)

    def test_ayni_kaynagin_birden_cok_isabeti_en_iyisini_kullanir(self) -> None:
        """Bir sayfa birden çok chunk'a bölünmüş olabilir; en iyi sıra geçerlidir."""
        assert metrics.mean_reciprocal_rank([_outcome("A", ((5, 2, 9),))]) == pytest.approx(0.5)


class TestCitationPrecision:
    def test_payda_atif_sayisidir_soru_sayisi_degil(self) -> None:
        outcomes = [
            metrics.CitationOutcome(item_id="A", shown=3, correct=2),
            metrics.CitationOutcome(item_id="B", shown=1, correct=1),
        ]
        precision, correct, shown = metrics.citation_precision(outcomes)
        assert (correct, shown) == (3, 4)
        assert precision == pytest.approx(0.75)

    def test_hic_atif_yoksa_oran_tanimsiz(self) -> None:
        """1.0 döndürmek 'hiç atıf yapmayan sistem kusursuz atıf yapıyor' demek olurdu."""
        precision, _, shown = metrics.citation_precision(
            [metrics.CitationOutcome(item_id="A", shown=0, correct=0)]
        )
        assert shown == 0
        assert precision is None


class TestRefusalMetrics:
    def test_karisiklik_matrisi_ve_f1(self) -> None:
        outcomes = [
            metrics.RefusalOutcome("A", expected_refusal=True, actual_refusal=True),  # TP
            metrics.RefusalOutcome("B", expected_refusal=True, actual_refusal=False),  # FN
            metrics.RefusalOutcome("C", expected_refusal=False, actual_refusal=True),  # FP
            metrics.RefusalOutcome("D", expected_refusal=False, actual_refusal=False),  # TN
            metrics.RefusalOutcome("E", expected_refusal=True, actual_refusal=True),  # TP
        ]
        confusion = metrics.refusal_confusion(outcomes)
        assert (confusion.true_positive, confusion.false_negative) == (2, 1)
        assert (confusion.false_positive, confusion.true_negative) == (1, 1)
        assert confusion.precision == pytest.approx(2 / 3)
        assert confusion.recall == pytest.approx(2 / 3)
        assert confusion.f1 == pytest.approx(2 / 3)

    def test_hic_ret_beklenmiyorsa_recall_tanimsiz(self) -> None:
        confusion = metrics.refusal_confusion(
            [metrics.RefusalOutcome("A", expected_refusal=False, actual_refusal=False)]
        )
        assert confusion.recall is None
        assert confusion.f1 is None


class TestPercentile:
    def test_dogrusal_aradegerleme(self) -> None:
        assert metrics.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)

    def test_tek_deger_ve_bos(self) -> None:
        assert metrics.percentile([7.0], 0.95) == pytest.approx(7.0)
        assert metrics.percentile([], 0.95) is None


class TestSignificance:
    def test_bootstrap_ayni_kolda_fark_sifir(self) -> None:
        arm = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
        result = metrics.paired_bootstrap(arm, arm, iterations=500)
        assert result.difference == pytest.approx(0.0)
        assert result.lower == pytest.approx(0.0)
        assert result.upper == pytest.approx(0.0)
        assert not result.excludes_zero

    def test_bootstrap_ayni_tohumla_ayni_sonucu_verir(self) -> None:
        """Rapordaki aralık koşudan koşuya oynamamalı."""
        baseline = [0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0]
        candidate = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
        first = metrics.paired_bootstrap(baseline, candidate, iterations=800, seed=7)
        second = metrics.paired_bootstrap(baseline, candidate, iterations=800, seed=7)
        assert (first.lower, first.upper) == (second.lower, second.upper)
        assert first.difference == pytest.approx(0.375)

    def test_bootstrap_esit_uzunluk_ister(self) -> None:
        with pytest.raises(ValueError, match="aynı sayıda"):
            metrics.paired_bootstrap([1.0], [1.0, 0.0])

    def test_mcnemar_yalniz_ayrisan_sorulari_sayar(self) -> None:
        baseline = [True, False, True, False, True]
        candidate = [True, True, False, True, True]
        result = metrics.mcnemar(baseline, candidate)
        assert (result.only_a_correct, result.only_b_correct) == (1, 2)
        assert 0.0 < result.p_value <= 1.0

    def test_mcnemar_ayrisma_yoksa_p_bir(self) -> None:
        arm = [True, False, True]
        assert metrics.mcnemar(arm, arm).p_value == pytest.approx(1.0)


class TestSourceMatching:
    """Beklenen kaynak ile dönen sonucun eşleşme kuralı."""

    def _item(self, *sources: goldset.SourceSpec) -> goldset.GoldItem:
        return goldset.GoldItem(
            id="X-1",
            question="soru",
            category="direct",
            expected_behavior="answered",
            expected_sources=sources,
        )

    def _result(self, file_name: str, page: int | None = None, slide: int | None = None):
        from backends import RetrievedItem

        return RetrievedItem(
            chunk_id=None,
            file_name=file_name,
            page_number=page,
            slide_number=slide,
            section_title=None,
            text="metin",
        )

    def test_sayfadaki_herhangi_bir_chunk_isabet_sayilir(self) -> None:
        item = self._item(goldset.SourceSpec(file_name="a.pdf", page_number=2))
        retrieved = [
            self._result("b.pdf", page=2),
            self._result("a.pdf", page=2),
            self._result("a.pdf", page=2),
        ]
        assert evaluate.rank_sources(item, retrieved) == ((2, 3),)

    def test_dosya_duzeyi_kaynak_sayfa_aramaz(self) -> None:
        """Kod dosyalarında sayfa yoktur; dosya adı eşleşmesi yeter."""
        item = self._item(goldset.SourceSpec(file_name="producer_consumer.py"))
        assert evaluate.rank_sources(item, [self._result("producer_consumer.py")]) == ((1,),)

    def test_yanlis_sayfa_isabet_degildir(self) -> None:
        item = self._item(goldset.SourceSpec(file_name="a.pdf", page_number=2))
        assert evaluate.rank_sources(item, [self._result("a.pdf", page=3)]) == ((),)

    def test_atif_kullanicinin_gordugu_konumdan_dogrulanir(self) -> None:
        """Gösterilen sayfa yanlışsa, iç chunk_id doğru olsa bile atıf yanlıştır."""
        item = self._item(goldset.SourceSpec(file_name="a.pdf", page_number=7))
        assert evaluate.citation_is_correct(
            {"file_name": "a.pdf", "location": "Sayfa 7", "quote": "..."}, item
        )
        assert not evaluate.citation_is_correct(
            {"file_name": "a.pdf", "location": "Sayfa 8", "quote": "..."}, item
        )
        assert not evaluate.citation_is_correct(
            {"file_name": "b.pdf", "location": "Sayfa 7", "quote": "..."}, item
        )

    def test_slayt_konumu_da_cozulur(self) -> None:
        item = self._item(goldset.SourceSpec(file_name="s.pptx", slide_number=5))
        assert evaluate.citation_is_correct(
            {"file_name": "s.pptx", "location": "Slayt 5", "quote": "..."}, item
        )


class TestConfigFingerprint:
    def test_zaman_damgasi_parmak_izini_degistirmez(self) -> None:
        """Değişseydi hiçbir koşu bir öncekinden devam edemezdi."""
        base = {
            "set": "holdout",
            "set_version": "1.0",
            "layer": "retrieval",
            "mode": "hybrid",
            "embedding_provider": "fastembed",
            "embedding_model": "e5",
            "retrieval": {"top_k": 8},
            "llm": {"primary": "groq"},
        }
        assert evaluate.config_fingerprint({**base, "run_id": "a", "started_at": "1"}) == (
            evaluate.config_fingerprint({**base, "run_id": "b", "started_at": "2"})
        )

    def test_ayar_degisimi_parmak_izini_degistirir(self) -> None:
        """Eski ayarla üretilmiş bir cevap yeni koşuya sızmamalı."""
        base = {
            "set": "holdout",
            "set_version": "1.0",
            "layer": "retrieval",
            "mode": "hybrid",
            "embedding_provider": "fastembed",
            "embedding_model": "e5",
            "retrieval": {"top_k": 8},
            "llm": {"primary": "groq"},
        }
        changed = {**base, "retrieval": {"top_k": 5}}
        assert evaluate.config_fingerprint(base) != evaluate.config_fingerprint(changed)


class TestGoldSetSelection:
    def test_retrieval_katmani_kapsam_disi_sorulari_almaz(self) -> None:
        """Beklenen kaynağı olmayan soru Recall'a girerse metriği yapay olarak düşürür."""
        gold = goldset.load(EVALUATION_ROOT / "gold_set" / "calibration.json")
        retrieval_items = evaluate.select_items(gold, "retrieval", None)
        e2e_items = evaluate.select_items(gold, "e2e", None)
        assert all(item.expected_sources for item in retrieval_items)
        assert not any(item.category == "out_of_scope" for item in retrieval_items)
        assert len(e2e_items) > len(retrieval_items)


class TestLeakFlags:
    def test_kod_blogu_ve_semafor_cagrisi_isaretlenir(self) -> None:
        assert evaluate.flag_patterns("```python\nx=1\n```", evaluate._LEAK_PATTERNS)
        assert evaluate.flag_patterns("önce wait(empty) çağır", evaluate._LEAK_PATTERNS)
        assert evaluate.flag_patterns("mutex.lock() yap", evaluate._LEAK_PATTERNS)

    def test_kaynakli_ipucu_isaretlenmez(self) -> None:
        """Liste dar tutuldu: geniş olsaydı meşru ipuçları da işaretlenirdi."""
        hint = (
            "Senkronizasyon notlarındaki sıralama kuralına bak (Sayfa 2): sinyal "
            "semaforu beklemesi kritik bölgenin neresinde olmalı?"
        )
        assert evaluate.flag_patterns(hint, evaluate._LEAK_PATTERNS) == []


class _FakeRetrievalBackend:
    """Harness'ın BORULARINI sınamak için sahte arka uç.

    Bu, "ölçümü mock'la yapma" kuralının istisnası değil: burada ölçülen şey
    retrieval kalitesi değil, harness'ın sıralamayı doğru okuyup okumadığı, devam
    dosyasını yazıp yazmadığı ve aynı soruyu iki kez sorup sormadığı. Gerçek koşu
    gerçek indekste yapılır (backends.RetrievalBackend), sahte bir retriever ile
    ölçülen Recall hiçbir şey söylemez.
    """

    def __init__(self, results_by_question: dict[str, list[object]]) -> None:
        self._results = results_by_question
        self.calls: list[str] = []

    async def run(self, question: str, course_id: object) -> list[object]:
        self.calls.append(question)
        return self._results.get(question, [])


class TestHarnessPlumbing:
    def _gold_item(self, item_id: str, question: str, page: int) -> goldset.GoldItem:
        return goldset.GoldItem(
            id=item_id,
            question=question,
            category="direct",
            expected_behavior="answered",
            expected_sources=(goldset.SourceSpec(file_name="a.pdf", page_number=page),),
        )

    def _chunk(self, page: int):
        from backends import RetrievedItem

        return RetrievedItem(
            chunk_id=None,
            file_name="a.pdf",
            page_number=page,
            slide_number=None,
            section_title=None,
            text="metin",
        )

    async def test_kosu_devam_dosyasina_yazar_ve_ayni_soruyu_iki_kez_sormaz(
        self, tmp_path: Path
    ) -> None:
        from uuid import uuid4

        items = [self._gold_item("A", "birinci", 1), self._gold_item("B", "ikinci", 2)]
        backend = _FakeRetrievalBackend(
            {"birinci": [self._chunk(9), self._chunk(1)], "ikinci": [self._chunk(5)]}
        )
        runner = evaluate.RateLimitedRunner(base_delay=0.01)
        progress = evaluate.ProgressLog(tmp_path / "p.jsonl")
        course_id = uuid4()

        first = await evaluate.run_retrieval_layer(items, backend, runner, progress, course_id)

        assert len(first) == 2
        assert backend.calls == ["birinci", "ikinci"]
        assert len(progress) == 2

        # İkinci koşu aynı devam dosyasını okur: hiçbir soru tekrar sorulmamalı.
        resumed = evaluate.ProgressLog(tmp_path / "p.jsonl")
        second = await evaluate.run_retrieval_layer(items, backend, runner, resumed, course_id)

        assert backend.calls == ["birinci", "ikinci"]  # yeni çağrı yok
        assert [entry["item_id"] for entry in second] == ["A", "B"]

    async def test_puanlama_siralamayi_dogru_okur(self, tmp_path: Path) -> None:
        from uuid import uuid4

        items = [self._gold_item("A", "birinci", 1), self._gold_item("B", "ikinci", 2)]
        backend = _FakeRetrievalBackend(
            {
                # 'birinci' sorusunda beklenen sayfa 2. sırada, 'ikinci'de hiç yok.
                "birinci": [self._chunk(9), self._chunk(1)],
                "ikinci": [self._chunk(5)],
            }
        )
        entries = await evaluate.run_retrieval_layer(
            items,
            backend,
            evaluate.RateLimitedRunner(base_delay=0.01),
            evaluate.ProgressLog(tmp_path / "p.jsonl"),
            uuid4(),
        )
        scored = evaluate.score_retrieval(entries)

        assert scored["recall_at_5"] == pytest.approx(0.5)
        assert scored["mrr"] == pytest.approx(0.25)  # (1/2 + 0) / 2
        assert scored["by_category"]["direct"]["n"] == 2

    async def test_bozuk_devam_satiri_kosuyu_dusurmez(self, tmp_path: Path) -> None:
        """Yarıda kesilmiş yazma tek satırı bozar; saatlerce süren koşu kaybedilmemeli."""
        path = tmp_path / "p.jsonl"
        path.write_text(
            '{"item_id": "A", "category": "direct"}\n{"item_id": "B", "kes\n',
            encoding="utf-8",
        )
        progress = evaluate.ProgressLog(path)
        assert "A" in progress
        assert "B" not in progress


class _RateLimitError(Exception):
    def __init__(self) -> None:
        super().__init__("429 Too Many Requests")


class TestRateLimitBackoff:
    async def test_429_sonrasi_ustel_geri_cekilip_yeniden_dener(self) -> None:
        attempts = {"count": 0}

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise _RateLimitError
            return "tamam"

        runner = evaluate.RateLimitedRunner(base_delay=0.01, max_retries=5)
        result, _ = await runner.run(flaky, "T-1")

        assert result == "tamam"
        assert attempts["count"] == 3
        assert runner.stats.retries == 2
        assert runner.stats.rate_limited == 2

    async def test_kalici_hata_denemeler_bitince_yukselir(self) -> None:
        async def always_limited() -> str:
            raise _RateLimitError

        runner = evaluate.RateLimitedRunner(base_delay=0.01, max_retries=2)
        with pytest.raises(_RateLimitError):
            await runner.run(always_limited, "T-2")
        assert runner.stats.failures == 1

    async def test_arka_uc_yoksa_yeniden_denenmez(self) -> None:
        """Eksik modül geçici bir hata değil; beş kez beklemek zaman kaybı olurdu."""
        from backends import BackendUnavailable

        async def missing() -> str:
            raise BackendUnavailable("yok")

        runner = evaluate.RateLimitedRunner(base_delay=5.0, max_retries=3)
        with pytest.raises(BackendUnavailable):
            await runner.run(missing, "T-3")
        assert runner.stats.retries == 0
