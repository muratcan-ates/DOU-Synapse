"""Ölçüm metrikleri — saf fonksiyonlar, yan etkisiz, veritabanısız.

Neden ayrı dosya: bu fonksiyonlar raporun omurgasıdır ve tanım belirsizliği jürinin
ilk saldırı noktasıdır. Ayrı ve saf tutulunca test edilebilirler; `apps/api/tests/
test_eval_metrics.py` her tanımı sabitliyor. Koşu kodunun içine gömülselerdi ancak
gerçek bir koşuyla sınanabilirlerdi ve o koşu da onları doğrulamak için değil
kullanmak için yapılırdı.

Tanımlar (raporda AYNEN bu şekilde yazılır):

- **Recall@k** — ilk k sonuç içinde beklenen kaynaklardan **en az biri** bulunan
  soruların oranı. `multi_chunk` için AYRICA **tam kapsama** oranı raporlanır:
  beklenen kaynakların HEPSİ ilk k'de. Hangi tanımın kullanıldığı her tabloda yazılır.
- **MRR** — ilk ilgili sonucun sırasının tersinin ortalaması (`1/rank`; isabet yoksa 0).
- **Citation precision** — doğru (dosya + sayfa) atıf sayısı / **gösterilen toplam atıf
  sayısı**. Payda soru sayısı değil, atıf sayısıdır.
- **Ret F1** — pozitif sınıf "reddedilmeli" (`out_of_scope` + `insufficient_context`).
  Precision, recall, F1 ve 2x2 karışıklık matrisi birlikte raporlanır.
- **p95** — sorgu yolu uçtan uca gecikmesinin 95. yüzdeliği (sıcak replikada).
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    """Tek bir sorunun retrieval sonucu.

    `ranks_by_source`: beklenen her kaynak için, o kaynağı karşılayan sonuçların
    1-tabanlı sıraları. Bir sayfa birden çok chunk'a bölünmüş olabilir ve sayfadaki
    chunk'lardan herhangi biri isabet sayılır — bu yüzden kaynak başına birden fazla
    sıra olabilir. Hiç isabet yoksa o kaynağın demeti boştur.
    """

    item_id: str
    category: str
    ranks_by_source: tuple[tuple[int, ...], ...]
    retrieved_count: int

    @property
    def first_hit_rank(self) -> int | None:
        ranks = [rank for source in self.ranks_by_source for rank in source]
        return min(ranks) if ranks else None

    def hit_at(self, k: int) -> bool:
        """En az bir beklenen kaynak ilk k içinde mi."""
        rank = self.first_hit_rank
        return rank is not None and rank <= k

    def fully_covered_at(self, k: int) -> bool:
        """Beklenen kaynakların HEPSİ ilk k içinde mi."""
        if not self.ranks_by_source:
            return False
        return all(any(rank <= k for rank in source) for source in self.ranks_by_source)


@dataclass(frozen=True, slots=True)
class RefusalOutcome:
    item_id: str
    expected_refusal: bool
    actual_refusal: bool


@dataclass(frozen=True, slots=True)
class CitationOutcome:
    item_id: str
    #: Kullanıcıya gösterilen atıf sayısı — ret F1'in aksine payda burası.
    shown: int
    #: Dosya adı ve konumu beklenen kaynaklarla eşleşen atıf sayısı.
    correct: int


@dataclass(frozen=True, slots=True)
class ConfusionMatrix:
    """Pozitif sınıf: "reddedilmeli"."""

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def precision(self) -> float | None:
        predicted = self.true_positive + self.false_positive
        return self.true_positive / predicted if predicted else None

    @property
    def recall(self) -> float | None:
        actual = self.true_positive + self.false_negative
        return self.true_positive / actual if actual else None

    @property
    def f1(self) -> float | None:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    def as_dict(self) -> dict[str, object]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "true_negative": self.true_negative,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Eşleştirilmiş bootstrap: iki kolun farkı ve %95 güven aralığı."""

    difference: float
    lower: float
    upper: float
    iterations: int
    seed: int
    confidence: float

    @property
    def excludes_zero(self) -> bool:
        """Aralık sıfırı dışlıyor mu. 'Anlamlı' KELİMESİ bundan otomatik çıkmaz."""
        return self.lower > 0 or self.upper < 0

    def as_dict(self) -> dict[str, object]:
        return {
            "difference": self.difference,
            "ci_lower": self.lower,
            "ci_upper": self.upper,
            "confidence": self.confidence,
            "iterations": self.iterations,
            "seed": self.seed,
            "excludes_zero": self.excludes_zero,
        }


@dataclass(frozen=True, slots=True)
class McNemarResult:
    """Yalnız iki kolun AYRIŞTIĞI sorular bilgi taşır; ikisi de doğru/yanlışsa taşımaz."""

    only_a_correct: int
    only_b_correct: int
    p_value: float

    def as_dict(self) -> dict[str, object]:
        return {
            "only_a_correct": self.only_a_correct,
            "only_b_correct": self.only_b_correct,
            "discordant": self.only_a_correct + self.only_b_correct,
            "p_value": self.p_value,
        }


@dataclass(slots=True)
class RetrievalMetrics:
    n_items: int
    recall_at_5: float | None
    recall_at_8: float | None
    mrr: float | None
    #: Yalnız çok kaynaklı sorular için: beklenen kaynakların hepsi ilk k'de mi.
    full_coverage_at_5: float | None
    full_coverage_at_8: float | None
    n_multi_source: int
    by_category: dict[str, dict[str, object]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "n_items": self.n_items,
            "recall_at_5": self.recall_at_5,
            "recall_at_8": self.recall_at_8,
            "mrr": self.mrr,
            "full_coverage_at_5": self.full_coverage_at_5,
            "full_coverage_at_8": self.full_coverage_at_8,
            "n_multi_source": self.n_multi_source,
            "by_category": self.by_category,
        }


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def recall_at_k(outcomes: Sequence[RetrievalOutcome], k: int) -> float | None:
    return _mean([1.0 if outcome.hit_at(k) else 0.0 for outcome in outcomes])


def full_coverage_at_k(outcomes: Sequence[RetrievalOutcome], k: int) -> float | None:
    """Yalnız birden çok beklenen kaynağı olan sorular üzerinde anlamlıdır."""
    multi = [outcome for outcome in outcomes if len(outcome.ranks_by_source) > 1]
    return _mean([1.0 if outcome.fully_covered_at(k) else 0.0 for outcome in multi])


def mean_reciprocal_rank(outcomes: Sequence[RetrievalOutcome]) -> float | None:
    return _mean(
        [(1.0 / outcome.first_hit_rank) if outcome.first_hit_rank else 0.0 for outcome in outcomes]
    )


def retrieval_metrics(outcomes: Sequence[RetrievalOutcome]) -> RetrievalMetrics:
    categories = sorted({outcome.category for outcome in outcomes})
    by_category: dict[str, dict[str, object]] = {}
    for category in categories:
        subset = [outcome for outcome in outcomes if outcome.category == category]
        by_category[category] = {
            "n": len(subset),
            "recall_at_5": recall_at_k(subset, 5),
            "recall_at_8": recall_at_k(subset, 8),
            "mrr": mean_reciprocal_rank(subset),
            "full_coverage_at_8": full_coverage_at_k(subset, 8),
        }

    return RetrievalMetrics(
        n_items=len(outcomes),
        recall_at_5=recall_at_k(outcomes, 5),
        recall_at_8=recall_at_k(outcomes, 8),
        mrr=mean_reciprocal_rank(outcomes),
        full_coverage_at_5=full_coverage_at_k(outcomes, 5),
        full_coverage_at_8=full_coverage_at_k(outcomes, 8),
        n_multi_source=sum(1 for o in outcomes if len(o.ranks_by_source) > 1),
        by_category=by_category,
    )


def citation_precision(outcomes: Sequence[CitationOutcome]) -> tuple[float | None, int, int]:
    """(oran, doğru atıf, gösterilen atıf).

    Payda GÖSTERİLEN ATIF SAYISIDIR, soru sayısı değil. Hiç atıf gösterilmediyse oran
    tanımsızdır — 1.0 döndürmek "hiç atıf yapmayan sistem kusursuz atıf yapıyor"
    demek olurdu.
    """
    shown = sum(outcome.shown for outcome in outcomes)
    correct = sum(outcome.correct for outcome in outcomes)
    return (correct / shown if shown else None), correct, shown


def refusal_confusion(outcomes: Sequence[RefusalOutcome]) -> ConfusionMatrix:
    return ConfusionMatrix(
        true_positive=sum(1 for o in outcomes if o.expected_refusal and o.actual_refusal),
        false_positive=sum(1 for o in outcomes if not o.expected_refusal and o.actual_refusal),
        false_negative=sum(1 for o in outcomes if o.expected_refusal and not o.actual_refusal),
        true_negative=sum(1 for o in outcomes if not o.expected_refusal and not o.actual_refusal),
    )


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Doğrusal aradeğerlemeli yüzdelik (NumPy'nin varsayılanıyla aynı tanım).

    Tanımın yazılı olması şart: p95 için en az üç yaygın tanım dolaşıyor ve hangisinin
    kullanıldığı söylenmeden verilen bir p95 karşılaştırılamaz.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_bootstrap(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    iterations: int = 10_000,
    seed: int = 20260809,
    confidence: float = 0.95,
) -> BootstrapResult:
    """Soru bazında EŞLEŞTİRİLMİŞ bootstrap; fark = aday - referans.

    Eşleştirme şart: iki kol aynı soruları görür, dolayısıyla bağımsız örneklem
    varsayan bir test buradaki korelasyonu görmezden gelir ve aralığı olduğundan
    geniş verir. Yeniden örnekleme SORU düzeyinde yapılır — iki kolun aynı sorudaki
    sonucu birlikte seçilir.

    `seed` sabittir: aynı veriyle aynı aralık çıkmalı, yoksa rapordaki sayı koşudan
    koşuya oynar ve kimse hangisinin doğru olduğunu söyleyemez.
    """
    if len(baseline) != len(candidate):
        raise ValueError("Eşleştirilmiş bootstrap iki kolda da aynı sayıda soru ister.")
    if not baseline:
        raise ValueError("Boş örneklem üzerinde bootstrap yapılamaz.")

    n = len(baseline)
    observed = (sum(candidate) - sum(baseline)) / n
    rng = random.Random(seed)  # noqa: S311  (kriptografik değil, yeniden üretilebilirlik için)
    differences: list[float] = []
    for _ in range(iterations):
        total = 0.0
        for _ in range(n):
            index = rng.randrange(n)
            total += candidate[index] - baseline[index]
        differences.append(total / n)

    differences.sort()
    tail = (1.0 - confidence) / 2
    return BootstrapResult(
        difference=observed,
        lower=differences[max(0, math.floor(tail * iterations))],
        upper=differences[min(iterations - 1, math.ceil((1 - tail) * iterations) - 1)],
        iterations=iterations,
        seed=seed,
        confidence=confidence,
    )


def mcnemar(baseline: Sequence[bool], candidate: Sequence[bool]) -> McNemarResult:
    """McNemar'ın tam (binom) testi; iki yönlü p değeri.

    Yaklaşık ki-kare biçimi değil tam biçim kullanılıyor: ayrışan soru sayısı n≈50'lik
    bir sette çoğu zaman tek haneli kalır ve ki-kare yaklaşımı o aralıkta güvenilmez.
    """
    if len(baseline) != len(candidate):
        raise ValueError("McNemar iki kolda da aynı sayıda soru ister.")
    only_a = sum(1 for a, b in zip(baseline, candidate, strict=True) if a and not b)
    only_b = sum(1 for a, b in zip(baseline, candidate, strict=True) if b and not a)
    discordant = only_a + only_b
    if discordant == 0:
        # İki kol her soruda aynı sonucu verdi: fark yok, p=1.
        return McNemarResult(only_a_correct=0, only_b_correct=0, p_value=1.0)

    smaller = min(only_a, only_b)
    tail = sum(math.comb(discordant, i) for i in range(smaller + 1)) * (0.5**discordant)
    return McNemarResult(
        only_a_correct=only_a,
        only_b_correct=only_b,
        p_value=min(1.0, 2 * tail),
    )


@dataclass(frozen=True, slots=True)
class AgreementResult:
    """İki bağımsız etiketleyicinin uyumu (T047).

    `raw` zorunlu, `kappa` bonustur. Ham uyum, ÇÖZÜM ÖNCESİ hâliyle raporlanır:
    anlaşmazlıklar tartışılıp karara bağlanır ama uyum oranı tartışmadan önceki
    etiketlerden hesaplanır. Sonrasından hesaplanan bir uyum her zaman %100 çıkar
    ve hiçbir şey ölçmez.
    """

    n: int
    agreed: int
    raw: float
    kappa: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "agreed": self.agreed,
            "raw_agreement": self.raw,
            "cohens_kappa": self.kappa,
        }


def label_agreement(first: Sequence[str], second: Sequence[str]) -> AgreementResult:
    """Ham uyum oranı ve (mümkünse) Cohen's kappa.

    Kappa, şansa bağlı uyumu düşer; iki etiketleyici de her şeye aynı etiketi
    verdiğinde beklenen uyum 1'e gider ve kappa tanımsız kalır — bu durumda None
    döner. Ham uyumu yine de raporlarız: tanımsız bir kappa, ölçülmüş bir uyumu
    geçersiz kılmaz.
    """
    if len(first) != len(second):
        raise ValueError("İki etiketleyici aynı sayıda cevabı etiketlemeli.")
    if not first:
        raise ValueError("Boş örneklemde uyum hesaplanamaz.")

    n = len(first)
    agreed = sum(1 for a, b in zip(first, second, strict=True) if a == b)
    raw = agreed / n

    labels = set(first) | set(second)
    expected = sum(
        (sum(1 for a in first if a == label) / n) * (sum(1 for b in second if b == label) / n)
        for label in labels
    )
    kappa = None if expected >= 1.0 else (raw - expected) / (1 - expected)
    return AgreementResult(n=n, agreed=agreed, raw=raw, kappa=kappa)
