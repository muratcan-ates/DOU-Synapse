"""E4 ikinci doğrulayıcı: puan gösterilmeden önce iki bağımsız değerlendirmenin uzlaştırılması.

Buradaki her şey saf karar mantığıdır — sağlayıcı, veritabanı, ağ yoktur. Sınanan
şey modelin pedagojik kalitesi DEĞİL, kapının kapalı kalması gereken durumlarda
kapalı kalmasıdır: ikinci koşu alınamadığında, dayanaksız geldiğinde ya da iki
kırılım hizalanamadığında puanın gösterilememesi.

Elle kurulmuş `GradingOutcome`lar `grade_with_llm`in gerçekten ürettiği şekli
taklit eder: rubrik varken toplam puan kırılımdan türetilir (FR-117), `earned`
her satırda `weight × score / 100`tür ve dayanak `evidence_chunk_id`de durur.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.modules.assessment.grading import GradingOutcome
from app.modules.assessment.second_pass import (
    DEFAULT_TOLERANCE_PERCENT,
    ReconcileReason,
    ReconcileVerdict,
    Reconciliation,
    criterion_tolerance,
    reconcile,
)
from app.schemas.assessment import RubricCriterionScore, RubricItem

POINT_A = "Adımları sırayla açıklar"
POINT_B = "Bitiş koşulunu açıklar"
POINT_C = "Karmaşıklığı tartışır"
EVIDENCE = UUID("11111111-1111-4111-8111-111111111111")
OTHER_EVIDENCE = UUID("22222222-2222-4222-8222-222222222222")

RUBRIC_40_60 = [RubricItem(point=POINT_A, weight=40), RubricItem(point=POINT_B, weight=60)]
RUBRIC_50_50 = [RubricItem(point=POINT_A, weight=50), RubricItem(point=POINT_B, weight=50)]
RUBRIC_SINGLE = [RubricItem(point=POINT_A, weight=100)]


def _row(point: str, weight: int, score: int, *, earned: int | None = None) -> RubricCriterionScore:
    """`grading._rubric_breakdown` ile aynı kuralla bir kırılım satırı kurar.

    `earned` yalnız "kırılım kendi içinde tutarsız" senaryosunda elle verilir;
    normal yolda ağırlık ve ölçüt puanından türetilir.
    """
    return RubricCriterionScore(
        point=point,
        weight=weight,
        score=score,
        earned=round(weight * score / 100) if earned is None else earned,
    )


def _outcome(
    rows: list[RubricCriterionScore] | None = None,
    *,
    evidence: UUID | None = EVIDENCE,
    graded: bool = True,
    score: int | None = None,
) -> GradingOutcome:
    """Bir değerlendirme sonucu kurar; toplam varsayılan olarak kırılımdan türetilir.

    `score` açıkça verilirse türetme atlanır — kayıttan bozuk okunmuş, toplamı
    satırlarıyla tutmayan bir sonucu taklit etmenin tek yolu budur.
    """
    breakdown = list(rows or [])
    derived = sum(row.earned for row in breakdown) if breakdown else score
    return GradingOutcome(
        graded=graded,
        score=derived if score is None else score,
        evidence_chunk_id=evidence,
        rubric_breakdown=breakdown,
    )


def _full_marks(rubric: list[RubricItem]) -> list[RubricCriterionScore]:
    return [_row(item.point, item.weight, 100) for item in rubric]


def _pair(a_score: int, b_score: int) -> tuple[GradingOutcome, GradingOutcome]:
    """Birincil her kalemden tam puan verir; ikincil verilen ölçüt puanlarını verir."""
    primary = _outcome(_full_marks(RUBRIC_40_60))
    secondary = _outcome([_row(POINT_A, 40, a_score), _row(POINT_B, 60, b_score)])
    return primary, secondary


def _samples() -> dict[ReconcileVerdict, Reconciliation]:
    """Her karardan birer örnek; kararların tamamı kapsansın diye tek yerde durur."""
    rows = _full_marks(RUBRIC_50_50)
    agreed = reconcile(_outcome(rows), _outcome(rows), rubric=RUBRIC_50_50)
    escalate = reconcile(
        _outcome([_row(POINT_A, 50, 100), _row(POINT_B, 50, 0)]),
        _outcome([_row(POINT_A, 50, 0), _row(POINT_B, 50, 100)]),
        rubric=RUBRIC_50_50,
    )
    inconclusive = reconcile(_outcome(rows), None, rubric=RUBRIC_50_50)
    return {
        agreed.verdict: agreed,
        escalate.verdict: escalate,
        inconclusive.verdict: inconclusive,
    }


# ---------------------------------------------------------------------------
# Uyum ve tolerans
# ---------------------------------------------------------------------------


def test_iki_kosu_her_kalemde_ayni_puani_verirse_puan_gosterilir() -> None:
    rows = _full_marks(RUBRIC_40_60)
    result = reconcile(_outcome(rows), _outcome(rows), rubric=RUBRIC_40_60)

    assert result.verdict is ReconcileVerdict.AGREED
    assert result.reason is ReconcileReason.AGREEMENT
    assert result.score_is_displayable is True
    assert result.displayable_score == 100
    assert result.exceeded_criteria == ()
    assert result.total_difference == 0
    assert [(item.point, item.weight, item.tolerance) for item in result.criteria] == [
        (POINT_A, 40, 4),
        (POINT_B, 60, 6),
    ]


@pytest.mark.parametrize(
    ("a_score", "b_score", "point", "tolerance"),
    [(90, 100, POINT_A, 4), (100, 90, POINT_B, 6)],
)
def test_toleransin_tam_sinirindaki_fark_uyum_sayilir(
    a_score: int, b_score: int, point: str, tolerance: int
) -> None:
    """Eşitlik aşma değildir; sınır iki farklı ağırlıkta ayrı ayrı sınanır."""
    result = reconcile(*_pair(a_score, b_score), rubric=RUBRIC_40_60)
    measured = {item.point: item for item in result.criteria}[point]

    assert measured.tolerance == tolerance
    assert measured.difference == tolerance
    assert measured.exceeded is False
    assert result.verdict is ReconcileVerdict.AGREED
    assert result.displayable_score == 100


@pytest.mark.parametrize(
    ("a_score", "b_score", "point", "tolerance", "difference"),
    [(88, 100, POINT_A, 4, 5), (100, 88, POINT_B, 6, 7)],
)
def test_toleransi_bir_puan_asan_fark_havale_edilir(
    a_score: int, b_score: int, point: str, tolerance: int, difference: int
) -> None:
    result = reconcile(*_pair(a_score, b_score), rubric=RUBRIC_40_60)

    assert result.verdict is ReconcileVerdict.ESCALATE
    assert result.reason is ReconcileReason.CRITERION_GAP
    assert result.score_is_displayable is False
    assert result.displayable_score is None
    assert [item.point for item in result.exceeded_criteria] == [point]
    assert (result.exceeded_criteria[0].difference, result.exceeded_criteria[0].tolerance) == (
        difference,
        tolerance,
    )
    # Toplam farkı toleransın altında: kalemi görmeyen bir doğrulayıcı bunu kaçırırdı.
    assert result.total_difference is not None
    assert result.total_tolerance is not None
    assert result.total_difference <= result.total_tolerance


def test_ayni_mutlak_fark_dar_kalemde_asar_genis_kalemde_asmaz() -> None:
    """Toleransın sabit olmadığının doğrudan kanıtı: 5 puan, iki ağırlıkta iki karar."""
    dar = reconcile(*_pair(88, 100), rubric=RUBRIC_40_60)  # ağırlık 40, tolerans 4
    genis = reconcile(*_pair(100, 92), rubric=RUBRIC_40_60)  # ağırlık 60, tolerans 6

    assert {item.point: item.difference for item in dar.criteria}[POINT_A] == 5
    assert {item.point: item.difference for item in genis.criteria}[POINT_B] == 5
    assert dar.verdict is ReconcileVerdict.ESCALATE
    assert genis.verdict is ReconcileVerdict.AGREED


def test_tek_kalemdeki_buyuk_fark_havale_edilir_ve_o_kalem_raporlanir() -> None:
    rubric = [
        RubricItem(point=POINT_A, weight=30),
        RubricItem(point=POINT_B, weight=30),
        RubricItem(point=POINT_C, weight=40),
    ]
    primary = _outcome(_full_marks(rubric))
    secondary = _outcome([_row(POINT_A, 30, 100), _row(POINT_B, 30, 0), _row(POINT_C, 40, 100)])
    result = reconcile(primary, secondary, rubric=rubric)

    assert result.verdict is ReconcileVerdict.ESCALATE
    assert result.reason is ReconcileReason.CRITERION_GAP
    assert [item.point for item in result.exceeded_criteria] == [POINT_B]
    assert result.exceeded_criteria[0].primary_earned == 30
    assert result.exceeded_criteria[0].secondary_earned == 0
    assert result.displayable_score is None


def test_toplam_ayni_ama_kalem_dagilimi_zitken_havale_edilir() -> None:
    """Toplam üzerinden bakan bir doğrulayıcının tamamen kör olduğu tuzak.

    İki koşu da 50 veriyor ama biri yalnız ilk kalemi, diğeri yalnız ikinci kalemi
    karşılanmış sayıyor. `agreed` dönmesi kusur olurdu.
    """
    primary = _outcome([_row(POINT_A, 50, 100), _row(POINT_B, 50, 0)])
    secondary = _outcome([_row(POINT_A, 50, 0), _row(POINT_B, 50, 100)])
    result = reconcile(primary, secondary, rubric=RUBRIC_50_50)

    assert (primary.score, secondary.score) == (50, 50)
    assert result.total_difference == 0
    assert result.verdict is ReconcileVerdict.ESCALATE
    assert result.reason is ReconcileReason.CRITERION_GAP
    assert {item.point for item in result.exceeded_criteria} == {POINT_A, POINT_B}
    assert result.displayable_score is None


def test_kalemler_toleranstayken_toplam_kapisi_karari_degistirmez() -> None:
    """Rubrikli kipte toplam farkı, kalem toleranslarının toplamını aşamaz.

    Her kalem tam sınırdayken toplam fark tam toplam toleransına oturur; bu bile
    `escalate` üretmez. Rubrikli kipte `total_gap` bu yüzden ulaşılamazdır.
    """
    primary = _outcome(_full_marks(RUBRIC_50_50))
    secondary = _outcome([_row(POINT_A, 50, 90), _row(POINT_B, 50, 90)])
    result = reconcile(primary, secondary, rubric=RUBRIC_50_50)

    assert all(item.difference == item.tolerance for item in result.criteria)
    assert result.total_difference == result.total_tolerance == 10
    assert result.verdict is ReconcileVerdict.AGREED
    assert result.reason is ReconcileReason.AGREEMENT


# ---------------------------------------------------------------------------
# Puanı gizleyen yollar
# ---------------------------------------------------------------------------


def test_ikinci_kosu_alinamadiginda_uyum_degil_belirsiz_doner() -> None:
    """Bu dosyanın varlık nedeni: sessizce tek koşuya dönme regresyonunun kilidi.

    `secondary=None` sağlayıcı hatası/kota/zaman aşımı demektir. `agreed` dönseydi
    ekranda iki doğrulayıcıdan geçmiş gibi duran, arkasında tek koşu olan bir puan
    kalırdı.
    """
    primary = _outcome(_full_marks(RUBRIC_50_50))
    result = reconcile(primary, None, rubric=RUBRIC_50_50)

    assert result.verdict is not ReconcileVerdict.AGREED
    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.SECONDARY_MISSING
    assert result.score_is_displayable is False
    assert result.displayable_score is None
    assert primary.score == 100  # Puan ortada duruyor ama taşınmıyor.
    assert result.criteria == ()
    assert result.total_difference is None


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("degerlendirilemedi", ReconcileReason.SECONDARY_UNGRADED),
        ("puansiz", ReconcileReason.SECONDARY_UNGRADED),
        ("dayanaksiz", ReconcileReason.SECONDARY_UNGROUNDED),
    ],
)
def test_kullanilamaz_ikinci_kosu_belirsizdir(case: str, reason: ReconcileReason) -> None:
    """Dayanaksız bir ikinci koşu "bağımsız ikinci görüş" değildir; `agreed` üretemez."""
    rows = _full_marks(RUBRIC_50_50)
    if case == "degerlendirilemedi":
        secondary = _outcome(graded=False)
    elif case == "puansiz":
        secondary = GradingOutcome(graded=True, score=None, evidence_chunk_id=EVIDENCE)
    else:
        secondary = _outcome(rows, evidence=None)

    result = reconcile(_outcome(rows), secondary, rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is reason
    assert result.displayable_score is None


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("degerlendirilemedi", ReconcileReason.PRIMARY_UNGRADED),
        ("puansiz", ReconcileReason.PRIMARY_UNGRADED),
        ("dayanaksiz", ReconcileReason.PRIMARY_UNGROUNDED),
    ],
)
def test_kullanilamaz_birincil_kosu_belirsizdir(case: str, reason: ReconcileReason) -> None:
    rows = _full_marks(RUBRIC_50_50)
    if case == "degerlendirilemedi":
        primary = _outcome(graded=False)
    elif case == "puansiz":
        primary = GradingOutcome(graded=True, score=None, evidence_chunk_id=EVIDENCE)
    else:
        primary = _outcome(rows, evidence=None)

    result = reconcile(primary, _outcome(rows), rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is reason
    assert result.displayable_score is None


def test_iki_taraf_da_bozukken_birincil_gerekcesi_raporlanir() -> None:
    """Gerekçe tek etikette toplanmaz: hangi tarafın onarılacağı ayrı durmalı."""
    bozuk = _outcome(graded=False)
    result = reconcile(bozuk, bozuk, rubric=RUBRIC_50_50)
    assert result.reason is ReconcileReason.PRIMARY_UNGRADED

    dayanaksiz = _outcome(_full_marks(RUBRIC_50_50), evidence=None)
    karma = reconcile(dayanaksiz, bozuk, rubric=RUBRIC_50_50)
    assert karma.reason is ReconcileReason.PRIMARY_UNGROUNDED


@pytest.mark.parametrize("side", ["birincil", "ikincil"])
def test_kirilim_rubrik_kalemiyle_eslesmezse_karsilastirilamaz(side: str) -> None:
    """İsim uyuşmazlığı: kırılım satırı hiçbir rubrik kalemine bağlanamıyor."""
    saglam = _full_marks(RUBRIC_50_50)
    kaymis = [_row(POINT_A, 50, 100), _row("Başka bir ölçüt", 50, 100)]
    primary = _outcome(kaymis if side == "birincil" else saglam)
    secondary = _outcome(saglam if side == "birincil" else kaymis)

    result = reconcile(primary, secondary, rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.NOT_COMPARABLE
    assert result.detail is not None
    assert result.detail.startswith(f"{side}: ")
    assert POINT_B in result.detail
    assert result.displayable_score is None


@pytest.mark.parametrize(
    ("case", "fragment"),
    [
        ("eksik", "kalem içeriyor"),
        ("fazla", "kalem içeriyor"),
        ("tekrarli", "birden çok kez puanlanmış"),
        ("agirlik", "ağırlığı"),
        ("earned", "tutmuyor"),
    ],
)
def test_bozuk_kirilim_karsilastirilamaz(case: str, fragment: str) -> None:
    """Eksik kalemi 0 sayıp devam etmek, ölçülmemiş bir farkı "uyum" diye raporlamaktır."""
    if case == "eksik":
        rows = [_row(POINT_A, 50, 100)]
    elif case == "fazla":
        rows = [*_full_marks(RUBRIC_50_50), _row(POINT_C, 50, 100)]
    elif case == "tekrarli":
        rows = [_row(POINT_A, 50, 100), _row(POINT_A, 50, 60)]
    elif case == "agirlik":
        rows = [_row(POINT_A, 40, 100), _row(POINT_B, 50, 100)]
    else:
        rows = [_row(POINT_A, 50, 100, earned=49), _row(POINT_B, 50, 100)]

    result = reconcile(_outcome(rows), _outcome(_full_marks(RUBRIC_50_50)), rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.NOT_COMPARABLE
    assert result.detail is not None
    assert fragment in result.detail


@pytest.mark.parametrize("case", ["tekrarli", "bos"])
def test_rubrik_olcut_adlari_baglanamazsa_karsilastirilamaz(case: str) -> None:
    """Belirsiz bir eşleşme üzerinden "uyuştular" demek, karşılaştırmayı hiç yapmamaktır."""
    ikinci = f" {POINT_A}" if case == "tekrarli" else " "
    rubric = [RubricItem(point=POINT_A, weight=50), RubricItem(point=ikinci, weight=50)]

    result = reconcile(
        _outcome(evidence=EVIDENCE, score=80),
        _outcome(evidence=EVIDENCE, score=80),
        rubric=rubric,
    )

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.NOT_COMPARABLE
    assert result.detail is not None
    assert "rubrik ölçüt adları" in result.detail
    assert result.same_evidence is True  # Kayıt için toplanan bilgi karardan bağımsız durur.


@pytest.mark.parametrize("kirilimli", ["birincil", "ikincil"])
def test_yalniz_bir_tarafta_kirilim_varsa_karsilastirilamaz(kirilimli: str) -> None:
    """Kırılımsız tarafın hangi kalemden kaç puan verdiği bilinmez.

    Gerekçe metni KIRILIMI OLMAYAN tarafı adlandırır: eğitmen hangi koşunun
    talimatı yok saydığını gerekçeden okuyabilmeli.
    """
    rows = _full_marks(RUBRIC_50_50)
    kirilimsiz = _outcome(evidence=EVIDENCE, score=100)
    primary = _outcome(rows) if kirilimli == "birincil" else kirilimsiz
    secondary = kirilimsiz if kirilimli == "birincil" else _outcome(rows)

    result = reconcile(primary, secondary, rubric=RUBRIC_50_50)

    eksik = "ikincil" if kirilimli == "birincil" else "birincil"
    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.NOT_COMPARABLE
    assert result.detail is not None
    assert result.detail.startswith(f"{eksik}: kırılım 0 kalem içeriyor")


@pytest.mark.parametrize("side", ["birincil", "ikincil"])
def test_gosterilen_puan_kalem_toplamiyla_tutmazsa_belirsizdir(side: str) -> None:
    """Toplam satırlarla ayrıştığında karşılaştırılacak iki ayrı "puan" olur."""
    rows = _full_marks(RUBRIC_50_50)
    bozuk = _outcome(rows, score=99)
    primary = bozuk if side == "birincil" else _outcome(rows)
    secondary = _outcome(rows) if side == "birincil" else bozuk

    result = reconcile(primary, secondary, rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.INCONCLUSIVE
    assert result.reason is ReconcileReason.INCONSISTENT_TOTAL
    assert result.detail is not None
    assert result.detail.startswith(f"{side}: ")
    assert "99" in result.detail and "100" in result.detail
    assert result.displayable_score is None


# ---------------------------------------------------------------------------
# Kırılımsız kip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rubric", [[], RUBRIC_50_50], ids=["rubriksiz", "rubrik_dolu"])
def test_iki_taraf_da_kirilimsizken_yalniz_toplam_karsilastirilir(
    rubric: list[RubricItem],
) -> None:
    """Talimatı yok sayan bir koşu kırılımsız dönebilir; bu meşru bir durumdur."""
    result = reconcile(
        _outcome(evidence=EVIDENCE, score=80),
        _outcome(evidence=EVIDENCE, score=88),
        rubric=rubric,
    )

    assert result.criteria == ()
    assert result.total_difference == 8
    assert result.total_tolerance == 10
    assert result.verdict is ReconcileVerdict.AGREED
    assert result.displayable_score == 80  # Ortalama değil, birincilin puanı.


def test_kirilimsiz_kipte_toplam_farki_havaleye_yol_acar() -> None:
    result = reconcile(
        _outcome(evidence=EVIDENCE, score=60),
        _outcome(evidence=EVIDENCE, score=75),
        rubric=[],
    )

    assert result.verdict is ReconcileVerdict.ESCALATE
    assert result.reason is ReconcileReason.TOTAL_GAP
    assert (result.total_difference, result.total_tolerance) == (15, 10)
    assert result.displayable_score is None


def test_bos_rubrik_cokmeden_anlamli_sonuc_verir() -> None:
    uyum = reconcile(
        _outcome(evidence=EVIDENCE, score=70), _outcome(evidence=EVIDENCE, score=70), rubric=[]
    )
    assert uyum.verdict is ReconcileVerdict.AGREED
    assert uyum.criteria == ()

    # Rubrik yokken gelen bir kırılımın ağırlıkları hiçbir şeye karşı doğrulanamaz.
    kirilimli = reconcile(
        _outcome(_full_marks(RUBRIC_50_50)), _outcome(_full_marks(RUBRIC_50_50)), rubric=[]
    )
    assert kirilimli.verdict is ReconcileVerdict.INCONCLUSIVE
    assert kirilimli.reason is ReconcileReason.NOT_COMPARABLE


@pytest.mark.parametrize(
    ("secondary_score", "verdict"),
    [(70, ReconcileVerdict.AGREED), (69, ReconcileVerdict.ESCALATE)],
)
def test_tek_kalemli_rubrik_cokmeden_anlamli_sonuc_verir(
    secondary_score: int, verdict: ReconcileVerdict
) -> None:
    """Tek kalemde tolerans 10'dur; sınır ve sınırın bir puan ötesi ayrı kararlardır."""
    result = reconcile(
        _outcome([_row(POINT_A, 100, 80)]),
        _outcome([_row(POINT_A, 100, secondary_score)]),
        rubric=RUBRIC_SINGLE,
    )

    assert len(result.criteria) == 1
    assert result.criteria[0].tolerance == 10
    assert result.verdict is verdict
    assert result.displayable_score == (80 if verdict is ReconcileVerdict.AGREED else None)


def test_tolerans_ham_agirliktan_degil_normalize_agirliktan_turer() -> None:
    """Ağırlıkları 100 etmeyen eski rubrikler okuma yolunda normalize edilir."""
    rubric = [RubricItem(point=POINT_A, weight=30), RubricItem(point=POINT_B, weight=30)]
    primary = _outcome([_row(POINT_A, 50, 100), _row(POINT_B, 50, 100)])

    uyum = reconcile(
        primary, _outcome([_row(POINT_A, 50, 90), _row(POINT_B, 50, 100)]), rubric=rubric
    )
    assert [item.weight for item in uyum.criteria] == [50, 50]  # ham 30 değil
    assert uyum.criteria[0].tolerance == 5  # 30'dan türeseydi 3 olurdu
    assert uyum.criteria[0].difference == 5
    assert uyum.verdict is ReconcileVerdict.AGREED

    havale = reconcile(
        primary, _outcome([_row(POINT_A, 50, 88), _row(POINT_B, 50, 100)]), rubric=rubric
    )
    assert havale.criteria[0].difference == 6
    assert havale.verdict is ReconcileVerdict.ESCALATE


# ---------------------------------------------------------------------------
# Sözleşmeler: mesaj, puan taşıma, eşik, dayanak
# ---------------------------------------------------------------------------


def test_ogrenci_mesaji_hicbir_kararda_puan_sizdirmaz() -> None:
    """`escalate` ve `inconclusive`te "iki koşu 30 puan ayrıştı" demek yarısını sızdırırdı."""
    samples = _samples()
    assert set(samples) == set(ReconcileVerdict)

    for verdict, result in samples.items():
        message = result.student_message
        assert message.strip()
        assert not any(char.isdigit() for char in message), verdict
        for sayisal in (result.displayable_score, result.total_difference, result.total_tolerance):
            assert sayisal is None or str(sayisal) not in message


def test_puan_yalniz_uyum_kararinda_tasinir() -> None:
    for verdict, result in _samples().items():
        gosterilebilir = verdict is ReconcileVerdict.AGREED
        assert result.score_is_displayable is gosterilebilir
        assert (result.displayable_score is not None) is gosterilebilir


@pytest.mark.parametrize("evidence", [EVIDENCE, OTHER_EVIDENCE, uuid4()])
def test_farkli_dayanak_chunk_tek_basina_havale_degildir(evidence: UUID) -> None:
    """Bağımsız iki değerlendiricinin farklı cümleye dayanması beklenir; kayda geçer."""
    rows = _full_marks(RUBRIC_50_50)
    result = reconcile(_outcome(rows), _outcome(rows, evidence=evidence), rubric=RUBRIC_50_50)

    assert result.verdict is ReconcileVerdict.AGREED
    assert result.same_evidence is (evidence == EVIDENCE)


@pytest.mark.parametrize("percent", [100, 101, 1000, -1])
def test_dogrulayiciyi_kapatan_tolerans_yuzdesi_reddedilir(percent: int) -> None:
    """Tolerans kalemin tüm genişliğine eşitlenirse kapı sessizce kapanırdı."""
    rows = _full_marks(RUBRIC_50_50)
    with pytest.raises(ValueError, match="tolerance_percent"):
        reconcile(_outcome(rows), _outcome(rows), rubric=RUBRIC_50_50, tolerance_percent=percent)

    # Doğrulama, ikinci koşu hiç yokken bile çalışır: hatalı eşik gizlenmez.
    with pytest.raises(ValueError, match="tolerance_percent"):
        reconcile(_outcome(rows), None, rubric=RUBRIC_50_50, tolerance_percent=percent)


@pytest.mark.parametrize(
    ("percent", "verdict"),
    [(0, ReconcileVerdict.ESCALATE), (DEFAULT_TOLERANCE_PERCENT, ReconcileVerdict.ESCALATE)],
)
def test_tolerans_yuzdesi_cagri_yerinden_daraltilabilir(
    percent: int, verdict: ReconcileVerdict
) -> None:
    """Kalibrasyon bu dosyayı değiştirmeyi gerektirmesin diye eşik dışarıdan verilebilir."""
    primary = _outcome(evidence=EVIDENCE, score=80)
    secondary = _outcome(evidence=EVIDENCE, score=99)

    assert reconcile(primary, secondary, rubric=[], tolerance_percent=percent).verdict is verdict
    genis = reconcile(primary, secondary, rubric=[], tolerance_percent=25)
    assert genis.verdict is ReconcileVerdict.AGREED
    assert genis.total_tolerance == 25


def test_sifir_tolerans_birebir_ayni_puanlari_yine_uyum_sayar() -> None:
    rows = _full_marks(RUBRIC_50_50)
    result = reconcile(_outcome(rows), _outcome(rows), rubric=RUBRIC_50_50, tolerance_percent=0)

    assert all(item.tolerance == 0 for item in result.criteria)
    assert result.verdict is ReconcileVerdict.AGREED


@pytest.mark.parametrize(
    ("weight", "expected"),
    [(1, 0), (5, 0), (9, 0), (10, 1), (40, 4), (45, 4), (50, 5), (60, 6), (100, 10)],
)
def test_criterion_tolerance_agirliktan_turer_ve_asagi_yuvarlar(weight: int, expected: int) -> None:
    """Aşağı yuvarlama bilinçlidir: şüpheli durumda tolerans büyümez (fail-closed)."""
    assert criterion_tolerance(weight) == expected
    assert criterion_tolerance(weight, percent=0) == 0
    assert criterion_tolerance(weight, percent=50) == weight // 2


def test_her_reconcile_reason_en_az_bir_yoldan_uretilir() -> None:
    """Üretilemeyen bir gerekçe ölü koddur: sayacı hiç artmayacak bir arıza etiketi."""
    rows = _full_marks(RUBRIC_50_50)
    produced = {
        reconcile(_outcome(rows), _outcome(rows), rubric=RUBRIC_50_50).reason,
        reconcile(
            _outcome([_row(POINT_A, 50, 100), _row(POINT_B, 50, 0)]),
            _outcome([_row(POINT_A, 50, 0), _row(POINT_B, 50, 100)]),
            rubric=RUBRIC_50_50,
        ).reason,
        reconcile(
            _outcome(evidence=EVIDENCE, score=10),
            _outcome(evidence=EVIDENCE, score=90),
            rubric=[],
        ).reason,
        reconcile(_outcome(rows), None, rubric=RUBRIC_50_50).reason,
        reconcile(_outcome(graded=False), _outcome(rows), rubric=RUBRIC_50_50).reason,
        reconcile(_outcome(rows), _outcome(graded=False), rubric=RUBRIC_50_50).reason,
        reconcile(_outcome(rows, evidence=None), _outcome(rows), rubric=RUBRIC_50_50).reason,
        reconcile(_outcome(rows), _outcome(rows, evidence=None), rubric=RUBRIC_50_50).reason,
        reconcile(
            _outcome([_row(POINT_A, 50, 100), _row(POINT_C, 50, 100)]),
            _outcome(rows),
            rubric=RUBRIC_50_50,
        ).reason,
        reconcile(_outcome(rows, score=99), _outcome(rows), rubric=RUBRIC_50_50).reason,
    }

    assert produced == set(ReconcileReason)
