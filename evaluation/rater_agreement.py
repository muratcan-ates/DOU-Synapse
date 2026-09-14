"""Sıralı rubrik puanları için ağırlıklı değerlendirici uyumu (E4'ün ölçüm yarısı).

Neden bu dosya var: `metrics.label_agreement` nominal Cohen's kappa hesaplar ve o
istatistik etiketler hakkında "aynı mı, değil mi" dışında hiçbir şey bilmez. Rubrik
puanı ise **sıralıdır**. İki değerlendiriciden biri 1, öteki 4 verdiyse rubriği
taban tabana zıt okumuşlardır; biri 3, öteki 4 verdiyse aslında aynı yerde durup
sınırda ayrılmışlardır. Nominal kappa ikisini de tek bir "anlaşamadılar" kutusuna
atar, dolayısıyla bu iki veriyi aynı sayıyla özetler. Ağırlıklı kappa tam olarak bu
ayrımı yapmak için vardır: her anlaşmazlığı, puanlar arasındaki **mesafeye** göre
cezalandırır. Kuadratik ağırlıkta ceza mesafenin karesiyle büyür, yani uzak
anlaşmazlıklar orantısız ağırlık taşır — rubrik uyumu bu yüzden kuadratik ağırlıkla
(QWK) raporlanır.

Nominal kappa yanlış olduğu için değil, **yanlış soruya cevap verdiği** için yeterli
değil. Bu modül onu silmiyor: rapor üçünü (nominal, lineer, kuadratik) yan yana
veriyor, çünkü aralarındaki fark tek başına bilgidir. Nominal düşük ama kuadratik
yüksekse, değerlendiriciler sık ama **az** ayrılıyor demektir; ikisi birlikte
düşükse ayrılıklar gerçekten uzaktır ve rubrik metni belirsizdir.

## Burada eşik YOKTUR ve bu bilinçlidir

`.ai` kuyruğundaki E4 maddesi "QWK eşiği insan-insan uyumuyla belirlenir" diyor.
Bunun anlamı şu: bir modelin insan puanlarıyla uyumu, **iki insanın birbiriyle
uyumundan** yüksek olamaz — o tavan, rubriğin ve görevin kendi belirsizliğidir.
Dolayısıyla "QWK >= 0.7 kabul edilir" gibi literatürden ödünç alınmış bir sabit
burada anlamsızdır: 0.7 bir rubrikte tavana yakın, başkasında erişilemez olabilir.

**Bu ölçüm henüz YAPILMADI.** Bu depoda iki bağımsız insanın aynı cevapları
rubrikle puanladığı bir oturum yok; `evaluation/faithfulness/score_labels.py`
üç kategorili *faithfulness* etiketlemesini kapsıyor, rubrik puanını değil.
Eşik, o oturum yapıldıktan sonra, ölçülen insan-insan QWK'sinden türetilir ve
o zaman buraya değil, eşiği kullanan kapıya yazılır. Bu dosya yalnız ölçer.

## Küçük n uyarısı

Kappa, tek bir maddenin oynamasına şaşırtıcı derecede duyarlıdır. n=20'de bir
maddenin puanı bir kategori kayarsa QWK çoğu zaman 0.05'ten fazla oynar; yani
"0.71 ölçtük" cümlesi n küçükken bir nokta değil, geniş bir aralıktır.
`agreement_report` bu yüzden noktayı tek başına vermez: maddeler üzerinden
bootstrap ile bir güven aralığı üretir ve `sample_size_warning` alanında bu
aralığın **genişliğini** sayı olarak raporlar. Metin yerine sayı, çünkü metin
uyarısı rapora kopyalanırken düşer; sayı sütunda kalır.

Bu modül saf ve veritabanısızdır; `metrics.py` gibi yalnız standart kütüphane
kullanır ve `apps/api/tests/test_rater_agreement.py` her tanımı sabitler.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

WeightScheme = Literal["nominal", "linear", "quadratic"]

#: Desteklenen ağırlık şemaları. `nominal` bilerek içeride: aynı kod yolundan
#: geçince nominal kappa ile ağırlıklı kappa'nın farkı uygulama farkı değil,
#: yalnız ağırlık farkı olur — rapordaki karşılaştırma ancak böyle dürüsttür.
WEIGHT_SCHEMES: tuple[WeightScheme, ...] = ("nominal", "linear", "quadratic")

#: Bootstrap tohumu sabittir: aynı veriyle aynı aralık çıkmalı. Oynayan bir
#: aralık, raporu okuyanın hangi koşuya bakacağını bilememesi demektir.
#: (`metrics.paired_bootstrap` da aynı gerekçeyle sabit tohum kullanıyor.)
DEFAULT_BOOTSTRAP_SEED = 20260913

#: 2000 yeniden örnekleme: aralığı DARALTMAZ (aralığın genişliği n'den gelir),
#: yalnız uçlarını oturtur. Daha büyük bir sayı raporu değiştirmez, testleri
#: yavaşlatır.
DEFAULT_BOOTSTRAP_ITERATIONS = 2000


@dataclass(frozen=True, slots=True)
class WeightedAgreementResult:
    """Tek bir ağırlık şemasıyla hesaplanmış uyum.

    Duruş `metrics.AgreementResult` ile aynı: `raw` zorunlu, `kappa` bonustur.
    Kappa tanımsız kaldığında (aşağıya bak) `None` döner ama `raw` yine dolar —
    tanımsız bir kappa, ölçülmüş bir uyumu geçersiz kılmaz.

    `observed_disagreement` / `expected_disagreement` rapora giriyor çünkü kappa
    bir ORANDIR ve payı paydasından ayırmadan okunamaz: 0.40 hem "gözlenen
    uyumsuzluk düşük" hem "şans uyumsuzluğu yüksek" yüzünden çıkabilir ve ikisi
    çok farklı hikâyelerdir.
    """

    n: int
    agreed: int
    raw: float
    kappa: float | None
    weights: str
    #: İlan edilmiş ölçek — gözlenen puanlar değil. Gözlenmeyen kategori de burada.
    categories: tuple[int, ...]
    observed_disagreement: float
    expected_disagreement: float

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "agreed": self.agreed,
            "raw_agreement": self.raw,
            "weights": self.weights,
            "weighted_kappa": self.kappa,
            "categories": list(self.categories),
            "observed_disagreement": self.observed_disagreement,
            "expected_disagreement": self.expected_disagreement,
        }


@dataclass(slots=True)
class AgreementReport:
    """Üç kappa, dağılım, karışıklık matrisi ve n — tek kayıtta.

    Üçü birden raporlanıyor çünkü tek bir sayı seçmek, seçimi rapordan gizlemek
    olurdu. Okuyan "hangi kappa?" diye sormak zorunda kalmasın diye hepsi
    yazılır ve hangisinin sıralı puan için doğru olduğu modül docstring'inde
    anlatılır.
    """

    n: int
    agreed: int
    raw: float
    categories: tuple[int, ...]
    nominal_kappa: float | None
    linear_kappa: float | None
    quadratic_kappa: float | None
    #: İlan edilmiş her kategori için sayım — kullanılmayanlar 0 ile görünür.
    first_distribution: dict[int, int]
    second_distribution: dict[int, int]
    #: `categories` sırasında, TAM BOYUTLU satır x sütun sayımları.
    confusion_matrix: tuple[tuple[int, ...], ...]
    quadratic_ci_lower: float | None
    quadratic_ci_upper: float | None
    #: Kuadratik kappa'nın bootstrap güven aralığının GENİŞLİĞİ. Eşik değildir,
    #: karşılaştırma sayısı da değildir: n küçükken büyür, büyüdükçe küçülür.
    #: Kappa tanımsızsa `None`.
    sample_size_warning: float | None
    bootstrap_iterations: int
    bootstrap_seed: int
    bootstrap_confidence: float
    #: Kappa'nın tanımsız kaldığı yeniden örnekleme sayısı. Kendisi bir
    #: kararsızlık işaretidir: sıfırdan büyükse örneklem tek kategoriye
    #: yığılacak kadar küçüktür.
    undefined_resamples: int

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "agreed": self.agreed,
            "raw_agreement": self.raw,
            "categories": list(self.categories),
            "nominal_kappa": self.nominal_kappa,
            "linear_weighted_kappa": self.linear_kappa,
            "quadratic_weighted_kappa": self.quadratic_kappa,
            "first_distribution": dict(self.first_distribution),
            "second_distribution": dict(self.second_distribution),
            "confusion_matrix": [list(row) for row in self.confusion_matrix],
            "quadratic_ci_lower": self.quadratic_ci_lower,
            "quadratic_ci_upper": self.quadratic_ci_upper,
            "sample_size_warning": self.sample_size_warning,
            "bootstrap_iterations": self.bootstrap_iterations,
            "bootstrap_seed": self.bootstrap_seed,
            "bootstrap_confidence": self.bootstrap_confidence,
            "undefined_resamples": self.undefined_resamples,
        }


def _weight(scheme: str, first_score: int, second_score: int) -> float:
    """İki puan arasındaki uyumsuzluk ağırlığı — NORMALİZE EDİLMEDEN.

    Literatürdeki tanım ağırlıkları `(maks - min)` ya da `(maks - min)^2` ile
    böler. Burada bölünmüyor çünkü kappa `1 - Do/De` oranıdır ve o sabit hem
    payda hem paydada aynı biçimde durup **sadeleşir**; bölmek sayıyı
    değiştirmez, yalnız tek kategorili bir ölçekte 0/0 riski yaratır.

    Yan etkisi yararlıdır: `observed_disagreement` kuadratik şemada ortalama
    **karesel puan farkı**, lineer şemada ortalama **mutlak fark**, nominal
    şemada ise doğrudan `1 - ham uyum` olur. Üçü de tek başına okunabilir
    sayılardır; 0'a 1'e sıkıştırılmış hâlleri değildir.
    """
    difference = abs(first_score - second_score)
    if scheme == "nominal":
        return 0.0 if difference == 0 else 1.0
    if scheme == "linear":
        return float(difference)
    return float(difference * difference)


def _validate(
    first: Sequence[int],
    second: Sequence[int],
    categories: Iterable[int] | None,
) -> tuple[int, ...]:
    """Girdiyi fail-closed doğrula ve ilan edilmiş kategori aralığını döndür.

    `categories` verilmezse gözlenen en küçük ve en büyük puan arasındaki **tam
    tamsayı aralığı** kurulur — gözlenen puanların kümesi değil. İkisi ağırlıklı
    kappa'nın sayısını değiştirmez (ağırlıklar puan değerinden hesaplanıyor,
    aşağıya bak) ama dağılım ve karışıklık matrisi bu aralığa göre boyutlanır;
    "hiçbir değerlendirici 2 vermedi" bilgisi ancak matris tam boyutluyken
    görünür, kategori satırı hiç yokken görünmez.
    """
    if len(first) != len(second):
        raise ValueError("İki değerlendirici aynı sayıda cevabı puanlamalı.")
    if not first:
        raise ValueError("Boş örneklemde uyum hesaplanamaz.")

    for label, scores in (("birinci", first), ("ikinci", second)):
        for index, score in enumerate(scores):
            # `bool` ayrıca eleniyor: Python'da `True` bir `int`'tir ve `isinstance`
            # tek başına onu geçirir. Hata ValueError kalıyor (TypeError değil):
            # `_validate` tek bir fail-closed kapıdır ve uzunluk, boşluk, ölçek
            # dışılık, tip — hepsi çağırana aynı istisnayla döner. Ayrıştırmak,
            # `except ValueError` yazan çağıranın tip hatasını kaçırması demekti.
            is_ordinal_int = isinstance(score, int) and not isinstance(score, bool)
            if not is_ordinal_int:
                raise ValueError(
                    f"Rubrik puanı sıralı tamsayı olmalı; {label} değerlendiricinin "
                    f"{index}. puanı {score!r}. Kesirli ya da mantıksal bir değeri "
                    "sessizce tamsayıya çevirmek, ölçülen mesafeyi değiştirirdi."
                )

    if categories is None:
        lowest = min(min(first), min(second))
        highest = max(max(first), max(second))
        return tuple(range(lowest, highest + 1))

    declared = tuple(sorted({int(value) for value in categories}))
    if not declared:
        raise ValueError("Kategori listesi boş olamaz.")
    outside = sorted({score for score in (*first, *second) if score not in declared})
    if outside:
        raise ValueError(
            f"Puanlar ilan edilen ölçeğin dışında: {outside} (ölçek: {list(declared)}). "
            "Ölçek dışı bir puan sessizce kabul edilirse rubrik ile veri arasındaki "
            "uyuşmazlık rapora değil, sayının içine gömülür."
        )
    return declared


def _kappa(
    first: Sequence[int],
    second: Sequence[int],
    categories: Sequence[int],
    scheme: str,
) -> tuple[float | None, float, float]:
    """(kappa, gözlenen ağırlıklı uyumsuzluk, beklenen ağırlıklı uyumsuzluk).

    Doğrulama yapmaz; bootstrap içinden binlerce kez çağrıldığı için ayrıldı.
    """
    n = len(first)
    observed = (
        sum(_weight(scheme, left, right) for left, right in zip(first, second, strict=True)) / n
    )

    first_counts = Counter(first)
    second_counts = Counter(second)
    expected = 0.0
    for row in categories:
        row_count = first_counts.get(row, 0)
        if row_count == 0:
            continue
        for column in categories:
            column_count = second_counts.get(column, 0)
            if column_count == 0:
                continue
            expected += (row_count / n) * (column_count / n) * _weight(scheme, row, column)

    if expected <= 0.0:
        # Şans eseri beklenen uyumsuzluk sıfır: iki değerlendirici de tek bir
        # kategoriye yığılmış. Kappa "şans üstü ne kadar uyum" sorusunun
        # cevabıdır ve şansın kendisi %100 uyum ürettiğinde soru anlamsızdır.
        return None, observed, expected
    return 1.0 - observed / expected, observed, expected


def weighted_kappa(
    first: Sequence[int],
    second: Sequence[int],
    *,
    weights: WeightScheme = "quadratic",
    categories: Iterable[int] | None = None,
) -> WeightedAgreementResult:
    """Sıralı tamsayı puanlar için ağırlıklı kappa.

    `weights`:

    - `"quadratic"` (varsayılan) — ceza puan farkının **karesiyle** büyür. Rubrik
      uyumu için standart olan budur (QWK): 1↔4 anlaşmazlığı 3↔4'ün dokuz katı
      ağırlık taşır.
    - `"linear"` — ceza mutlak farkla doğru orantılı; 1↔4, 3↔4'ün üç katı.
    - `"nominal"` — mesafeyi hiç görmez ve tam olarak Cohen's kappa'ya eşittir.
      Karşılaştırma için var; sıralı puan raporlanırken kullanılmamalıdır.

    ## Gözlenmemiş kategori tuzağı

    Bu, QWK uygulamalarının klasik ve **sessiz** hatasıdır. Karışıklık matrisi
    genellikle "veride görülen etiketler" listesi üzerine kurulur ve ağırlıklar o
    listedeki **konum** farkından hesaplanır. Rubrik 1-4 iken kimse 3 vermediyse
    liste `[1, 2, 4]` olur; konum farkıyla 2↔4 arası bir adım, 1↔2 arası da bir
    adımdır. Yani atlanan kategori, uzak bir anlaşmazlığı yakın gibi gösterir.
    Sonuç yanlış çıkar, hiçbir hata mesajı vermez ve rapora girer.

    Somut örnek (bu testlerdeki veriyle aynı): `[1, 2, 4, 4]` ve `[1, 2, 4, 1]`
    için doğru QWK 2/5 = 0.4'tür; konum farkıyla hesaplanırsa 5/13 ≈ 0.385 çıkar.

    Bu modül ağırlıkları konumdan değil **puan değerinden** hesaplar, bu yüzden
    hata yapısal olarak imkânsızdır. `categories` yine de işe yarar:
    (a) rubriğin ilan edilmiş ölçeğini kayda geçirir, (b) ölçek dışına düşen bir
    puanı (1-4 rubriğinde 7) sessizce kabul etmez, (c) dağılımın ve karışıklık
    matrisinin tam boyutlu olmasını sağlar.

    ## Tanımsız kaldığı durumlar

    Beklenen uyumsuzluk sıfırlanırsa kappa tanımsızdır ve `kappa=None` döner:
    ölçekte tek kategori ilan edilmişse ya da iki değerlendirici de her cevaba
    aynı puanı vermişse. Ham uyum bu durumda da doldurulur.

    Hata: iki dizi farklı uzunluktaysa, biri boşsa, puanlar tamsayı değilse ya da
    ilan edilen ölçeğin dışındaysa `ValueError`.
    """
    if weights not in WEIGHT_SCHEMES:
        raise ValueError(f"Bilinmeyen ağırlık şeması: {weights!r}; beklenen {WEIGHT_SCHEMES}.")

    declared = _validate(first, second, categories)
    n = len(first)
    agreed = sum(1 for left, right in zip(first, second, strict=True) if left == right)
    kappa, observed, expected = _kappa(first, second, declared, weights)
    return WeightedAgreementResult(
        n=n,
        agreed=agreed,
        raw=agreed / n,
        kappa=kappa,
        weights=weights,
        categories=declared,
        observed_disagreement=observed,
        expected_disagreement=expected,
    )


def _bootstrap_quadratic(
    first: Sequence[int],
    second: Sequence[int],
    categories: Sequence[int],
    *,
    iterations: int,
    seed: int,
    confidence: float,
) -> tuple[float | None, float | None, int]:
    """Maddeler üzerinden eşleştirilmiş bootstrap; (alt, üst, tanımsız sayısı).

    Yeniden örnekleme MADDE düzeyindedir: bir madde seçildiğinde iki
    değerlendiricinin o maddedeki puanı birlikte gelir. Ayrı ayrı örneklenselerdi
    eşleşme bozulur ve ölçülen şey artık uyum olmazdı.

    Küçük örneklemde bazı yeniden örneklemeler tek kategoriye yığılır ve kappa
    orada tanımsız kalır. Bunlar aralığa sokulmaz ama SAYILIR: sayının kendisi
    "örneklem bu istatistiği taşıyamayacak kadar küçük" demenin sayısal hâlidir.
    """
    n = len(first)
    # Kriptografik amaçlı değil: sabit tohumla yeniden üretilebilirlik için.
    rng = random.Random(seed)  # noqa: S311
    values: list[float] = []
    undefined = 0
    for _ in range(iterations):
        indexes = [rng.randrange(n) for _ in range(n)]
        resampled_first = [first[index] for index in indexes]
        resampled_second = [second[index] for index in indexes]
        kappa, _, _ = _kappa(resampled_first, resampled_second, categories, "quadratic")
        if kappa is None:
            undefined += 1
            continue
        values.append(kappa)

    if not values:
        return None, None, undefined

    values.sort()
    count = len(values)
    tail = (1.0 - confidence) / 2
    lower = values[max(0, math.floor(tail * count))]
    upper = values[min(count - 1, math.ceil((1 - tail) * count) - 1)]
    return lower, upper, undefined


def agreement_report(
    first: Sequence[int],
    second: Sequence[int],
    *,
    categories: Iterable[int] | None = None,
    iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> AgreementReport:
    """Ham uyum, üç kappa, dağılım, karışıklık matrisi, n ve aralık genişliği.

    Neden hepsi tek kayıtta: bu sayılar ancak birlikte okunduğunda yanıltmaz.
    Tek başına bir QWK, dağılım görünmeden değerlendirilemez — iki değerlendirici
    de puanların %90'ını tek kategoriye yığmışsa yüksek ham uyum kendiliğinden
    gelir ve kappa onu düzeltmeye çalışırken aşırı tepki verir (kappa'nın bilinen
    "prevalans" sorunu). n görünmeden hiçbiri değerlendirilemez.

    `sample_size_warning`, kuadratik kappa için bootstrap güven aralığının
    genişliğidir. Bir eşik ya da kabul ölçütü DEĞİLDİR; "bu noktaya ne kadar
    güvenilir" sorusunun sayısal cevabıdır ve n büyüdükçe küçülür. Kappa
    tanımsızsa `None` olur ve bootstrap hiç koşmaz (`bootstrap_iterations=0`).

    Bu rapor bir KARAR vermez. E4'ün eşiği, insan-insan uyumu ölçüldükten sonra,
    bu raporun çıktısına bakılarak dışarıda belirlenir — modül docstring'ine bak.
    """
    declared = _validate(first, second, categories)
    n = len(first)
    agreed = sum(1 for left, right in zip(first, second, strict=True) if left == right)

    nominal = _kappa(first, second, declared, "nominal")[0]
    linear = _kappa(first, second, declared, "linear")[0]
    quadratic = _kappa(first, second, declared, "quadratic")[0]

    first_counts = Counter(first)
    second_counts = Counter(second)
    pair_counts = Counter(zip(first, second, strict=True))
    confusion = tuple(
        tuple(pair_counts.get((row, column), 0) for column in declared) for row in declared
    )

    lower: float | None = None
    upper: float | None = None
    undefined = 0
    performed = 0
    if quadratic is not None:
        lower, upper, undefined = _bootstrap_quadratic(
            first,
            second,
            declared,
            iterations=iterations,
            seed=seed,
            confidence=confidence,
        )
        performed = iterations

    warning = None if lower is None or upper is None else upper - lower
    return AgreementReport(
        n=n,
        agreed=agreed,
        raw=agreed / n,
        categories=declared,
        nominal_kappa=nominal,
        linear_kappa=linear,
        quadratic_kappa=quadratic,
        first_distribution={category: first_counts.get(category, 0) for category in declared},
        second_distribution={category: second_counts.get(category, 0) for category in declared},
        confusion_matrix=confusion,
        quadratic_ci_lower=lower,
        quadratic_ci_upper=upper,
        sample_size_warning=warning,
        bootstrap_iterations=performed,
        bootstrap_seed=seed,
        bootstrap_confidence=confidence,
        undefined_resamples=undefined,
    )
