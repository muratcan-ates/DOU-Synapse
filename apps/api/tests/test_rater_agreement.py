"""Ağırlıklı değerlendirici uyumunun tanımlarını sabitleyen testler (E4).

Neden API test paketinin içinde: `evaluation/rater_agreement.py` raporun uyum
sayılarını üretiyor ve ölçüm aracının sessizce yanlış sayı üretmesi, ölçülen
sistemin hatasından daha tehlikelidir — ölçülen sistemin hatası raporda görünür,
ölçüm aracının hatası raporu kendisi yazar. `test_eval_metrics.py` ile aynı
gerekçe, aynı import yolu.

Her test bir TANIMI sabitler. "QWK neydi ve nominal kappa'dan nerede ayrılır?"
sorusunun cevabı burada koşan koddur.

Bu dosya veritabanına ve ağa DOKUNMAZ; `rater_agreement` saf ve yalnız standart
kütüphaneye bağımlıdır.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

EVALUATION_ROOT = Path(__file__).resolve().parents[3] / "evaluation"
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

import metrics  # noqa: E402
import rater_agreement  # noqa: E402

# --------------------------------------------------------------------------------------
# Testlerde tekrar tekrar kullanılan veri kümeleri. İsimlendirme bilerek açık:
# hangi veri hangi olguyu gösteriyor, çağrı yerinde okunabilsin.
# --------------------------------------------------------------------------------------

#: Elle hesaplanmış referans tablo (3 kategori, n=6). Adım adım hesap
#: `TestReferansHesap` içinde.
REFERENCE_FIRST = [1, 1, 2, 2, 3, 3]
REFERENCE_SECOND = [1, 1, 2, 3, 3, 1]

#: UZAK anlaşmazlık: iki madde 1↔4 ayrışıyor (mesafe 3).
FAR_FIRST = [1, 1, 4, 4, 2, 2, 3, 3]
FAR_SECOND = [1, 4, 4, 1, 2, 2, 3, 3]

#: YAKIN anlaşmazlık: iki madde 3↔4 ayrışıyor (mesafe 1).
#: UZAK ile aynı n'e, aynı ham uyuma (6/8) ve AYNI marjinallere sahip —
#: her kategori iki değerlendiricide de tam 2 kez geçiyor. Tek fark mesafedir,
#: dolayısıyla iki veri arasındaki her kappa farkı YALNIZ ağırlıktan gelir.
NEAR_FIRST = [3, 3, 4, 4, 1, 1, 2, 2]
NEAR_SECOND = [3, 4, 4, 3, 1, 1, 2, 2]

#: Bootstrap testleri için yeterince dağınık, 16 maddelik bir puanlama.
SPREAD_FIRST = [3, 1, 4, 2, 4, 3, 2, 1, 3, 4, 2, 1, 4, 3, 1, 2]
SPREAD_SECOND = [3, 2, 4, 2, 3, 3, 1, 1, 4, 4, 2, 2, 4, 2, 1, 3]


def _normalized_kappa(
    first: Sequence[int],
    second: Sequence[int],
    categories: Sequence[int],
    *,
    power: int,
) -> float:
    """Literatürdeki NORMALİZE ağırlıklarla kappa — bağımsız ikinci uygulama.

    Ağırlık `(|i-j| / (maks - min)) ** power`; bitişik bir ölçekte `(maks - min)`
    tam olarak `(k-1)`'dir, yani kuadratikte `(i-j)^2/(k-1)^2`, lineerde
    `|i-j|/(k-1)`. Modül bu sabitle BÖLMÜYOR; bu yardımcı, bölmemenin sayıyı
    gerçekten değiştirmediğini sınamak için var (bkz. `TestAgirlikMatrisi`).
    """
    span = categories[-1] - categories[0]
    n = len(first)

    def weight(left: int, right: int) -> float:
        return (abs(left - right) / span) ** power

    observed = sum(weight(a, b) for a, b in zip(first, second, strict=True)) / n
    expected = sum(
        (list(first).count(i) / n) * (list(second).count(j) / n) * weight(i, j)
        for i in categories
        for j in categories
    )
    return 1.0 - observed / expected


def _positional_kappa(first: Sequence[int], second: Sequence[int]) -> float:
    """QWK'nın KLASİK HATASI: ağırlıkları puan değerinden değil, gözlenen
    etiketler listesindeki KONUMDAN hesaplayan uygulama.

    Burada bilerek yanlış yazıldı. Doğru sayının bu yanlış sayıya eşit
    OLMADIĞINI göstermek için gerekli; yoksa "ağırlıklar puan değerinden
    hesaplanıyor" cümlesi test edilmemiş bir iddia olarak kalırdı.
    """
    observed_labels = sorted(set(first) | set(second))
    index = {label: position for position, label in enumerate(observed_labels)}
    n = len(first)

    def weight(left: int, right: int) -> float:
        return float((index[left] - index[right]) ** 2)

    observed = sum(weight(a, b) for a, b in zip(first, second, strict=True)) / n
    expected = sum(
        (list(first).count(i) / n) * (list(second).count(j) / n) * weight(i, j)
        for i in observed_labels
        for j in observed_labels
    )
    return 1.0 - observed / expected


class TestAgirlikMatrisi:
    """Ağırlık yasasının kendisi — kappa'ya girmeden önce."""

    def test_agirlik_semalari_beklenen_mesafe_yasasini_izler(self) -> None:
        """`observed_disagreement` her şemada tek başına okunabilir bir sayıdır.

        Kuadratikte ortalama KARESEL puan farkı, lineerde ortalama MUTLAK fark,
        nominalde `1 - ham uyum`. Ağırlık yasası bozulursa bu üç sayı bozulur;
        kappa'nın kendisi oran olduğu için bazı bozulmaları yutabilir.
        """
        first, second = REFERENCE_FIRST, REFERENCE_SECOND
        differences = [abs(a - b) for a, b in zip(first, second, strict=True)]
        n = len(first)

        quadratic = rater_agreement.weighted_kappa(first, second, weights="quadratic")
        linear = rater_agreement.weighted_kappa(first, second, weights="linear")
        nominal = rater_agreement.weighted_kappa(first, second, weights="nominal")

        assert quadratic.observed_disagreement == pytest.approx(sum(d * d for d in differences) / n)
        assert linear.observed_disagreement == pytest.approx(sum(differences) / n)
        assert nominal.observed_disagreement == pytest.approx(1.0 - nominal.raw)

    def test_normalizasyon_sabiti_kappayi_degistirmez(self) -> None:
        """Modül `(k-1)` ile bölmüyor; bölen bağımsız bir uygulama aynı sayıyı vermeli.

        Kappa `1 - Do/De` oranıdır, sabit hem payda hem paydada durup sadeleşir.
        Bu testin işi o cebiri sözden sayıya çevirmek: eşitlik bozulursa modülün
        docstring'indeki gerekçe yanlış demektir.
        """
        categories = (1, 2, 3, 4)
        for scheme, power in (("quadratic", 2), ("linear", 1)):
            module = rater_agreement.weighted_kappa(
                FAR_FIRST, FAR_SECOND, weights=scheme, categories=categories
            )
            reference = _normalized_kappa(FAR_FIRST, FAR_SECOND, categories, power=power)
            assert module.kappa == pytest.approx(reference), scheme

    def test_tek_kategorili_olcekte_sifira_bolme_yok(self) -> None:
        """k=1 iken `(k-1)` sıfırdır; normalize eden bir uygulama burada patlardı.

        Modül bölmediği için patlamaz, ama beklenen uyumsuzluk da sıfırlanır:
        kappa tanımsızdır. Ham uyum yine raporlanır.
        """
        result = rater_agreement.weighted_kappa([2, 2, 2], [2, 2, 2], categories=[2])
        assert result.categories == (2,)
        assert result.kappa is None
        assert result.expected_disagreement == pytest.approx(0.0)
        assert result.raw == pytest.approx(1.0)

        report = rater_agreement.agreement_report([2, 2, 2], [2, 2, 2], categories=[2])
        assert report.confusion_matrix == ((3,),)
        assert report.quadratic_kappa is None


class TestSiraliCezalandirma:
    """QWK'nın VAR OLMA NEDENİ: mesafe bilgisi."""

    def test_uzak_anlasmazlik_yakindan_daha_cok_cezalandirilir(self) -> None:
        """1↔4 ayrışması, 3↔4 ayrışmasından daha ağır cezalandırılmalı.

        İki veri kümesi kasıtlı olarak EŞLEŞTİRİLDİ: aynı n (8), aynı ham uyum
        (6/8), aynı marjinaller (her kategori iki tarafta da 2 kez). Geriye tek
        fark kalıyor — anlaşmazlığın MESAFESİ.

        Sonuç, nominal kappa'nın neden yetmediğinin kanıtıdır: nominal iki veri
        için AYNI sayıyı (2/3) verir, çünkü "aynı mı değil mi" dışında bir şey
        görmez. QWK 0.1 ile 0.9'u ayırt eder.
        """
        far = rater_agreement.agreement_report(FAR_FIRST, FAR_SECOND, iterations=0)
        near = rater_agreement.agreement_report(NEAR_FIRST, NEAR_SECOND, iterations=0)

        assert far.raw == pytest.approx(near.raw)
        assert far.first_distribution == near.first_distribution
        assert far.second_distribution == near.second_distribution

        assert far.nominal_kappa == pytest.approx(near.nominal_kappa)
        assert far.nominal_kappa == pytest.approx(2 / 3)

        assert far.quadratic_kappa == pytest.approx(0.1)
        assert near.quadratic_kappa == pytest.approx(0.9)
        assert far.quadratic_kappa < near.quadratic_kappa

    def test_kuadratik_uzak_anlasmazligi_lineerden_daha_sert_cezalandirir(self) -> None:
        """Kuadratik ceza mesafenin karesiyle büyür; lineer yalnız mesafeyle.

        Aynı iki veri kümesinde bu, TEK YÖNLÜ bir kayma değildir: uzak
        anlaşmazlıkta kuadratik daha aşağı, yakın anlaşmazlıkta daha yukarı
        gider. Yani "kuadratik hep daha düşük" demek yanlış olurdu.
        """
        far_quadratic = rater_agreement.weighted_kappa(FAR_FIRST, FAR_SECOND).kappa
        far_linear = rater_agreement.weighted_kappa(FAR_FIRST, FAR_SECOND, weights="linear").kappa
        near_quadratic = rater_agreement.weighted_kappa(NEAR_FIRST, NEAR_SECOND).kappa
        near_linear = rater_agreement.weighted_kappa(
            NEAR_FIRST, NEAR_SECOND, weights="linear"
        ).kappa

        assert far_quadratic is not None and far_linear is not None
        assert near_quadratic is not None and near_linear is not None
        assert far_quadratic < far_linear
        assert near_quadratic > near_linear
        assert (far_linear, near_linear) == (pytest.approx(0.4), pytest.approx(0.8))

    def test_kuadratik_ve_lineer_ayni_veride_farkli_sayi_verir(self) -> None:
        """Referans tabloda üç şema üç ayrı sayı üretir; şema seçimi rapora yazılmalı."""
        report = rater_agreement.agreement_report(REFERENCE_FIRST, REFERENCE_SECOND, iterations=0)
        assert report.quadratic_kappa == pytest.approx(4 / 9)
        assert report.linear_kappa == pytest.approx(8 / 17)
        assert report.quadratic_kappa != pytest.approx(report.linear_kappa)


class TestNominalIleKarsilastirma:
    """`metrics.label_agreement` ile aynı veri üzerinde yüzleştirme."""

    def test_nominal_sema_metrics_label_agreement_ile_ayni_sayidir(self) -> None:
        """Nominal şema Cohen's kappa'nın TA KENDİSİ olmalı.

        Depoda iki ayrı uygulama var; ikisi aynı istatistiği hesaplıyorsa aynı
        sayıyı vermek zorundalar. Vermiyorlarsa biri bozuktur ve hangisi olduğu
        raporda değil, burada anlaşılmalı.
        """
        existing = metrics.label_agreement(
            [str(score) for score in REFERENCE_FIRST],
            [str(score) for score in REFERENCE_SECOND],
        )
        nominal = rater_agreement.weighted_kappa(
            REFERENCE_FIRST, REFERENCE_SECOND, weights="nominal"
        )
        assert existing.kappa is not None
        assert nominal.kappa == pytest.approx(existing.kappa)
        assert (nominal.n, nominal.agreed) == (existing.n, existing.agreed)
        assert nominal.raw == pytest.approx(existing.raw)

    def test_nominal_kappa_ile_qwk_ayni_veride_farklidir(self) -> None:
        """Sıralı puanda nominal kappa YANLIŞ SORUYA cevap verir.

        Aynı veri, aynı kod yolu, tek fark ağırlık: `label_agreement` 1/2 der,
        QWK 4/9. Fark tesadüf değil, mesafenin hesaba girmesidir.
        """
        existing = metrics.label_agreement(
            [str(score) for score in REFERENCE_FIRST],
            [str(score) for score in REFERENCE_SECOND],
        )
        quadratic = rater_agreement.weighted_kappa(REFERENCE_FIRST, REFERENCE_SECOND)
        assert existing.kappa == pytest.approx(0.5)
        assert quadratic.kappa == pytest.approx(4 / 9)
        assert quadratic.kappa != pytest.approx(existing.kappa)


class TestGozlenmemisKategori:
    """QWK uygulamalarının klasik ve SESSİZ hatası."""

    def test_agirlik_konumdan_degil_puan_degerinden_hesaplanir(self) -> None:
        """Kimse 3 vermediğinde 2↔4 arası bir adım gibi görünmemeli.

        `[1, 2, 4, 4]` / `[1, 2, 4, 1]` için doğru QWK 2/5 = 0.4'tür. Gözlenen
        etiketler listesindeki KONUM farkıyla hesaplanırsa 5/13 ≈ 0.385 çıkar:
        4↔1 anlaşmazlığı iki adım sayılır, oysa rubrikte üç adımdır. Hiçbir hata
        mesajı verilmez, sayı sessizce yanlış olur ve rapora girer.
        """
        first, second = [1, 2, 4, 4], [1, 2, 4, 1]
        result = rater_agreement.weighted_kappa(first, second, categories=[1, 2, 3, 4])
        assert result.kappa == pytest.approx(0.4)
        assert _positional_kappa(first, second) == pytest.approx(5 / 13)
        assert result.kappa != pytest.approx(_positional_kappa(first, second))

    def test_kategori_verilmediginde_bosluk_yine_de_doldurulur(self) -> None:
        """`categories` yokken ölçek gözlenen küme değil, TAM TAMSAYI ARALIĞIDIR.

        Atlanan 3 kategorisi çıkarsanan ölçeğe giriyor; hata bu yüzden yapısal
        olarak imkânsız, `categories` vermeyi unutan çağrı yerinde bile.
        """
        explicit = rater_agreement.weighted_kappa(
            [1, 2, 4, 4], [1, 2, 4, 1], categories=[1, 2, 3, 4]
        )
        inferred = rater_agreement.weighted_kappa([1, 2, 4, 4], [1, 2, 4, 1])
        assert inferred.categories == (1, 2, 3, 4)
        assert inferred.kappa == pytest.approx(explicit.kappa)

    def test_ilan_edilmis_olcek_matrisi_tam_boyutlu_tutar(self) -> None:
        """Rubrik 1-5 iken veri yalnız 2-3'te toplanmışsa matris 5x5 kalmalı.

        Kappa DEĞİŞMEZ — marjinali sıfır olan kategori ne paya ne paydaya
        katkı verir, bu doğru davranıştır. Değişen, raporun görünürlüğüdür:
        "hiçbir değerlendirici 1, 4 ya da 5 vermedi" bilgisi ancak matris ve
        dağılım tam boyutluyken okunur, kategori satırı hiç yokken okunmaz.
        """
        first, second = [2, 2, 3, 3, 2, 3], [2, 3, 3, 3, 2, 2]
        narrow = rater_agreement.agreement_report(first, second, iterations=0)
        wide = rater_agreement.agreement_report(
            first, second, categories=[1, 2, 3, 4, 5], iterations=0
        )

        assert narrow.categories == (2, 3)
        assert len(narrow.confusion_matrix) == 2

        assert wide.categories == (1, 2, 3, 4, 5)
        assert len(wide.confusion_matrix) == 5
        assert all(len(row) == 5 for row in wide.confusion_matrix)
        assert wide.first_distribution == {1: 0, 2: 3, 3: 3, 4: 0, 5: 0}
        assert wide.second_distribution == {1: 0, 2: 3, 3: 3, 4: 0, 5: 0}

        assert wide.quadratic_kappa == pytest.approx(narrow.quadratic_kappa)
        assert sum(sum(row) for row in wide.confusion_matrix) == wide.n

    def test_olcek_disi_puan_sessizce_kabul_edilmez(self) -> None:
        """1-4 rubriğinde 7 puanı bir veri hatasıdır; sayının içine gömülmemeli."""
        with pytest.raises(ValueError, match="ölçeğin dışında"):
            rater_agreement.weighted_kappa([1, 7], [1, 2], categories=[1, 2, 3, 4])


class TestReferansHesap:
    """Elle, kâğıt üstünde yapılmış hesabın koda sabitlenmesi.

    Tablo (satır = birinci değerlendirici, sütun = ikinci), kategoriler 1, 2, 3::

            j=1  j=2  j=3     toplam
      i=1    2    0    0        2
      i=2    0    1    1        2
      i=3    1    0    1        2
      -----------------------------
      top.   3    1    2        6

    Marjinaller: p = (1/3, 1/3, 1/3),  q = (1/2, 1/6, 1/3).

    KUADRATİK
      Gözlenen uyumsuzluk  Do = (0 + 0 + 0 + 1 + 0 + 4) / 6 = 5/6
      Beklenen uyumsuzluk  De = Σ p_i q_j (i-j)^2
        i=1: (1/3)·[(1/2)·0 + (1/6)·1 + (1/3)·4] = (1/3)·(3/2)  =  9/18
        i=2: (1/3)·[(1/2)·1 + (1/6)·0 + (1/3)·1] = (1/3)·(5/6)  =  5/18
        i=3: (1/3)·[(1/2)·4 + (1/6)·1 + (1/3)·0] = (1/3)·(13/6) = 13/18
        De = 27/18 = 3/2
      kappa = 1 - (5/6)/(3/2) = 1 - 5/9 = 4/9 ≈ 0.4444

    LİNEER
      Do = (0 + 0 + 0 + 1 + 0 + 2) / 6 = 1/2
      De = 5/18 + 5/18 + 7/18 = 17/18
      kappa = 1 - (1/2)·(18/17) = 8/17 ≈ 0.4706

    NOMİNAL
      Do = 2/6 = 1/3
      De = 1 - Σ p_i q_i = 1 - [(1/3)(1/2) + (1/3)(1/6) + (1/3)(1/3)] = 2/3
      kappa = 1 - (1/3)/(2/3) = 1/2
    """

    def test_kuadratik_referans_degeri(self) -> None:
        result = rater_agreement.weighted_kappa(REFERENCE_FIRST, REFERENCE_SECOND)
        assert result.observed_disagreement == pytest.approx(5 / 6)
        assert result.expected_disagreement == pytest.approx(3 / 2)
        assert result.kappa == pytest.approx(4 / 9)
        assert (result.n, result.agreed) == (6, 4)
        assert result.raw == pytest.approx(2 / 3)

    def test_lineer_referans_degeri(self) -> None:
        result = rater_agreement.weighted_kappa(REFERENCE_FIRST, REFERENCE_SECOND, weights="linear")
        assert result.observed_disagreement == pytest.approx(1 / 2)
        assert result.expected_disagreement == pytest.approx(17 / 18)
        assert result.kappa == pytest.approx(8 / 17)

    def test_nominal_referans_degeri(self) -> None:
        result = rater_agreement.weighted_kappa(
            REFERENCE_FIRST, REFERENCE_SECOND, weights="nominal"
        )
        assert result.observed_disagreement == pytest.approx(1 / 3)
        assert result.expected_disagreement == pytest.approx(2 / 3)
        assert result.kappa == pytest.approx(1 / 2)


class TestSinirDurumlari:
    def test_mukemmel_uyumda_kappa_bir(self) -> None:
        """Her maddede aynı puan + ölçekte birden çok kategori kullanılmış."""
        scores = [1, 2, 3, 4, 2, 3]
        result = rater_agreement.weighted_kappa(scores, list(scores))
        assert result.observed_disagreement == pytest.approx(0.0)
        assert result.expected_disagreement > 0.0
        assert result.kappa == pytest.approx(1.0)
        assert result.raw == pytest.approx(1.0)

    def test_tamamen_ters_uyumda_kappa_negatif(self) -> None:
        """Şans eseri beklenenden DAHA KÖTÜ uyum negatif kappa verir.

        `[1,1,4,4]` ile `[4,4,1,1]`: gözlenen uyumsuzluk 9, beklenen 4.5,
        yani kappa = 1 - 9/4.5 = -1.0. Ölçeğin alt ucu budur.
        """
        result = rater_agreement.weighted_kappa([1, 1, 4, 4], [4, 4, 1, 1])
        assert result.kappa is not None
        assert result.kappa < 0
        assert result.kappa == pytest.approx(-1.0)
        assert result.raw == pytest.approx(0.0)

    def test_beklenen_uyum_bir_iken_kappa_tanimsiz_ham_uyum_dolu(self) -> None:
        """İki değerlendirici de her şeye aynı puanı verdiyse şans uyumu 1'dir.

        Kappa "şans üstü ne kadar uyum" sorusunun cevabıdır; şansın kendisi %100
        uyum ürettiğinde soru anlamsızdır. Tanımsız bir kappa, ölçülmüş bir uyumu
        geçersiz kılmaz — `raw` yine 1.0 raporlanır.
        """
        for categories in (None, [1, 2, 3, 4]):
            result = rater_agreement.weighted_kappa(
                [3, 3, 3, 3], [3, 3, 3, 3], categories=categories
            )
            assert result.kappa is None
            assert result.raw == pytest.approx(1.0)
            assert result.agreed == 4
            assert result.expected_disagreement == pytest.approx(0.0)

    def test_bos_ornek_ve_farkli_uzunluk_reddedilir(self) -> None:
        with pytest.raises(ValueError, match="Boş örneklemde"):
            rater_agreement.weighted_kappa([], [])
        with pytest.raises(ValueError, match="aynı sayıda"):
            rater_agreement.weighted_kappa([1], [1, 2])
        with pytest.raises(ValueError, match="aynı sayıda"):
            rater_agreement.agreement_report([1, 2], [1])

    def test_tek_eleman(self) -> None:
        """n=1'de kappa hesaplanabilir ama hiçbir şey söylemez.

        Aynı puan verilmişse beklenen uyumsuzluk sıfırdır ve kappa tanımsız
        kalır. Farklı puan verilmişse gözlenen uyumsuzluk beklenenin TAMAMIDIR
        (tek madde marjinalleri de belirler), yani kappa sıfır çıkar — yüksek
        değil, düşük de değil, bilgisiz.
        """
        same = rater_agreement.weighted_kappa([2], [2])
        assert (same.n, same.kappa, same.raw) == (1, None, pytest.approx(1.0))

        different = rater_agreement.weighted_kappa([1], [3])
        assert different.categories == (1, 2, 3)
        assert different.kappa == pytest.approx(0.0)
        assert different.raw == pytest.approx(0.0)

    def test_tamsayi_olmayan_puan_reddedilir(self) -> None:
        """Kesirli ya da mantıksal bir değeri sessizce tamsayıya çevirmek mesafeyi bozar."""
        with pytest.raises(ValueError, match="sıralı tamsayı"):
            rater_agreement.weighted_kappa([1.0, 2.0], [1, 2])
        with pytest.raises(ValueError, match="sıralı tamsayı"):
            rater_agreement.weighted_kappa([True, False], [1, 0])
        with pytest.raises(ValueError, match="sıralı tamsayı"):
            rater_agreement.weighted_kappa([1, 2], ["1", "2"])

    def test_bilinmeyen_agirlik_semasi_reddedilir(self) -> None:
        """Tanınmayan bir şema sessizce kuadratiğe düşmemeli."""
        with pytest.raises(ValueError, match="Bilinmeyen ağırlık şeması"):
            rater_agreement.weighted_kappa([1, 2], [1, 2], weights="cubic")  # type: ignore[arg-type]


class TestRaporSozlesmesi:
    def test_as_dict_metrics_uslubuyla_uyumlu(self) -> None:
        """`metrics.AgreementResult.as_dict()` ile ortak alanlar AYNI adı taşımalı.

        İki uyum kaydı aynı rapora giriyor; biri `raw_agreement`, öteki
        `raw` yazarsa tabloyu birleştiren kod ikisini ayrı sütun sanar.
        """
        existing = metrics.label_agreement(["a", "b"], ["a", "a"]).as_dict()
        weighted = rater_agreement.weighted_kappa([1, 2], [1, 1]).as_dict()
        shared = {"n", "agreed", "raw_agreement"}
        assert shared <= set(existing)
        assert shared <= set(weighted)
        assert {key: weighted[key] for key in shared} == {key: existing[key] for key in shared}

        assert set(weighted) == {
            "n",
            "agreed",
            "raw_agreement",
            "weights",
            "weighted_kappa",
            "categories",
            "observed_disagreement",
            "expected_disagreement",
        }
        # Kappa adı nominalden AYRI: `cohens_kappa` ile `weighted_kappa` aynı
        # sütunda buluşursa hangi istatistik olduğu kaybolur.
        assert "cohens_kappa" in existing
        assert "cohens_kappa" not in weighted

    def test_rapor_json_serilestirilebilir(self) -> None:
        """Rapor dosyaya yazılıyor; `tuple` ve `Counter` sızarsa orada patlardı."""
        report = rater_agreement.agreement_report(
            REFERENCE_FIRST, REFERENCE_SECOND, iterations=50, seed=1
        )
        payload = json.loads(json.dumps(report.as_dict()))
        assert payload["categories"] == [1, 2, 3]
        assert payload["confusion_matrix"] == [[2, 0, 0], [0, 1, 1], [1, 0, 1]]
        assert payload["nominal_kappa"] == pytest.approx(1 / 2)
        assert payload["linear_weighted_kappa"] == pytest.approx(8 / 17)
        assert payload["quadratic_weighted_kappa"] == pytest.approx(4 / 9)

    def test_karisiklik_matrisi_satirlari_birinci_degerlendiricidir(self) -> None:
        """Devrik bir matris sessizce yanlış okunur; yön burada sabitleniyor.

        Veri asimetrik seçildi: simetrik bir örnekte devriklik görünmezdi.
        """
        report = rater_agreement.agreement_report([1, 1, 2], [2, 1, 2], iterations=0)
        assert report.categories == (1, 2)
        assert report.confusion_matrix == ((1, 1), (0, 1))
        assert [sum(row) for row in report.confusion_matrix] == [2, 1]
        assert list(report.first_distribution.values()) == [2, 1]
        assert list(report.second_distribution.values()) == [1, 2]

    def test_rapor_uc_kappayi_birlikte_verir(self) -> None:
        """Tek bir sayı seçmek, seçimi rapordan gizlemek olurdu."""
        report = rater_agreement.agreement_report(REFERENCE_FIRST, REFERENCE_SECOND, iterations=0)
        for scheme, value in (
            ("nominal", report.nominal_kappa),
            ("linear", report.linear_kappa),
            ("quadratic", report.quadratic_kappa),
        ):
            standalone = rater_agreement.weighted_kappa(
                REFERENCE_FIRST, REFERENCE_SECOND, weights=scheme
            )
            assert value == pytest.approx(standalone.kappa), scheme

    def test_raporda_kabul_esigi_ya_da_karar_alani_yok(self) -> None:
        """E4'ün eşiği insan-insan uyumu ölçüldükten sonra DIŞARIDA belirlenir.

        Literatürden ödünç alınmış bir sabit (örn. "QWK >= 0.7 kabul") burada
        anlamsızdır: 0.7 bir rubrikte tavana yakın, başkasında erişilemez
        olabilir. Rapor ölçer, karar vermez — bu yüzden çıktısında hiçbir
        mantıksal karar alanı olmamalı.
        """
        payload = rater_agreement.agreement_report(
            REFERENCE_FIRST, REFERENCE_SECOND, iterations=50, seed=1
        ).as_dict()
        assert not [key for key, value in payload.items() if isinstance(value, bool)]

        forbidden = ("threshold", "esik", "eşik", "accept", "kabul", "passed", "verdict")
        names = [name for name in dir(rater_agreement) if not name.startswith("__")]
        assert not [name for name in names if any(word in name.lower() for word in forbidden)]


class TestBootstrap:
    def test_ayni_tohum_ayni_araligi_verir(self) -> None:
        """Rapordaki aralık koşudan koşuya oynamamalı."""
        first = rater_agreement.agreement_report(
            SPREAD_FIRST, SPREAD_SECOND, iterations=400, seed=7
        )
        second = rater_agreement.agreement_report(
            SPREAD_FIRST, SPREAD_SECOND, iterations=400, seed=7
        )
        assert (first.quadratic_ci_lower, first.quadratic_ci_upper) == (
            second.quadratic_ci_lower,
            second.quadratic_ci_upper,
        )
        assert first.sample_size_warning == pytest.approx(
            first.quadratic_ci_upper - first.quadratic_ci_lower
        )
        assert first.bootstrap_seed == 7
        assert first.bootstrap_iterations == 400

    def test_farkli_tohum_farkli_aralik_verir(self) -> None:
        """Aralık gerçekten yeniden örneklemeden geliyor mu.

        Sabit tohumu test etmek tek başına yetmez: aralığı veriden değil sabit
        bir formülden üreten bir uygulama da o testi geçerdi.
        """
        first = rater_agreement.agreement_report(
            SPREAD_FIRST, SPREAD_SECOND, iterations=400, seed=7
        )
        other = rater_agreement.agreement_report(
            SPREAD_FIRST, SPREAD_SECOND, iterations=400, seed=99
        )
        assert (first.quadratic_ci_lower, first.quadratic_ci_upper) != (
            other.quadratic_ci_lower,
            other.quadratic_ci_upper,
        )

    def test_varsayilan_tohum_ve_yineleme_sabittir(self) -> None:
        """Çağrı yeri tohum vermezse de rapor yeniden üretilebilir olmalı."""
        assert rater_agreement.DEFAULT_BOOTSTRAP_SEED == 20260913
        assert rater_agreement.DEFAULT_BOOTSTRAP_ITERATIONS == 2000
        report = rater_agreement.agreement_report([1, 2, 3], [1, 2, 2], iterations=10)
        assert report.bootstrap_seed == rater_agreement.DEFAULT_BOOTSTRAP_SEED
        assert report.bootstrap_confidence == pytest.approx(0.95)

    def test_aralik_genisligi_kucuk_orneklemde_buyuktur(self) -> None:
        """`sample_size_warning` bir eşik değil, n'e duyarlı bir GENİŞLİKTİR.

        Aynı ampirik dağılım, iki farklı n: 8 maddede aralık geniş, aynı
        dağılımın 64 maddelik hâlinde dar. Karşılaştırma kontrollüdür — veri
        değişmiyor, yalnız örneklem büyüklüğü değişiyor.
        """
        small = rater_agreement.agreement_report(
            SPREAD_FIRST[:8], SPREAD_SECOND[:8], iterations=800, seed=4
        )
        large = rater_agreement.agreement_report(
            SPREAD_FIRST * 4, SPREAD_SECOND * 4, iterations=800, seed=4
        )
        assert small.n == 8
        assert large.n == 64
        assert small.sample_size_warning is not None
        assert large.sample_size_warning is not None
        assert large.sample_size_warning < small.sample_size_warning

    def test_kappa_tanimsizsa_bootstrap_hic_kosmaz(self) -> None:
        """Tanımsız bir noktanın etrafında aralık üretmek anlamsız olurdu."""
        report = rater_agreement.agreement_report([3, 3, 3], [3, 3, 3], iterations=500, seed=2)
        assert report.quadratic_kappa is None
        assert report.bootstrap_iterations == 0
        assert report.quadratic_ci_lower is None
        assert report.quadratic_ci_upper is None
        assert report.sample_size_warning is None
        assert report.undefined_resamples == 0
        assert report.raw == pytest.approx(1.0)

    def test_tanimsiz_yeniden_ornekleme_sayilir(self) -> None:
        """Bazı yeniden örneklemeler tek kategoriye yığılır; sayı kararsızlık işaretidir.

        n=3 ve iki kategorili bir veride, bir yeniden örneklemenin tek kategoriye
        yığılma olasılığı (2/3)^3 + (1/3)^3 = 1/3'tür. Bunlar aralığa sokulmaz
        ama SAYILIR — sıfırdan büyük bir sayı, örneklemin bu istatistiği
        taşıyamayacak kadar küçük olduğunun sayısal hâlidir.
        """
        report = rater_agreement.agreement_report([1, 1, 2], [1, 1, 2], iterations=600, seed=3)
        assert report.quadratic_kappa == pytest.approx(1.0)
        assert 0 < report.undefined_resamples < 600
        assert report.undefined_resamples == pytest.approx(600 / 3, rel=0.25)
        assert report.quadratic_ci_lower is not None

    def test_aralik_nokta_tahmini_kapsar(self) -> None:
        """Gözlenen kappa, kendi bootstrap aralığının içinde kalmalı."""
        report = rater_agreement.agreement_report(
            SPREAD_FIRST, SPREAD_SECOND, iterations=600, seed=13
        )
        assert report.quadratic_kappa is not None
        assert report.quadratic_ci_lower is not None
        assert report.quadratic_ci_upper is not None
        assert report.quadratic_ci_lower <= report.quadratic_kappa <= report.quadratic_ci_upper
        assert math.isfinite(report.sample_size_warning or math.nan)
