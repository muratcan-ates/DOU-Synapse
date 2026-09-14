"""Rubrik ölçütü eşlemesi Türkçe büyük/küçük harfte kırılmaz (L8 bulgusu, 14 Eylül 2026).

`str.casefold()` Türkçe için yanlıştır: "ADIMLARI" → "adimlari", "Adımları" →
"adımları". Model ölçüt adını büyük harfle döndürdüğünde eşleme kaçıyor ve 100
alan cevap sessizce 0 yazılıyordu. Eşleme artık `text_tr.fold` ile yapılır ve
hiçbir satır eşleşmezse kırılım "yok" sayılır, cevap sıfırlanmaz.
"""

from __future__ import annotations

from uuid import uuid4

from app.modules.assessment.grading import (
    _LlmVerdict,
    _rubric_breakdown,
    _RubrikSatiri,
    grounded_criterion_is_valid,
)
from app.schemas.assessment import (
    GroundedCriterionEvidence,
    OpenPayload,
    RubricCriterionScore,
    RubricItem,
)


def _payload(*points: tuple[str, int]) -> OpenPayload:
    # model_construct: yalnız rubrik alanı gerekir; doğrulama bu testin konusu değil.
    return OpenPayload.model_construct(rubric=[RubricItem(point=p, weight=w) for p, w in points])


def _verdict(*rows: tuple[str, int]) -> _LlmVerdict:
    return _LlmVerdict.model_construct(rubrik=[_RubrikSatiri(olcut=o, puan=p) for o, p in rows])


def test_buyuk_harfli_turkce_olcut_adi_eslesir() -> None:
    payload = _payload(("Adımları açıkla", 60), ("Sonucu yaz", 40))
    verdict = _verdict(("ADIMLARI AÇIKLA", 100), ("SONUCU YAZ", 100))

    breakdown = _rubric_breakdown(payload, verdict)

    assert [(row.point, row.score, row.earned) for row in breakdown] == [
        ("Adımları açıkla", 100, 60),
        ("Sonucu yaz", 100, 40),
    ]


def test_kucuk_i_ve_noktasiz_i_ayni_anahtara_iner() -> None:
    payload = _payload(("Isı iletimi", 100))
    verdict = _verdict(("ısı İLETİMİ", 80))

    breakdown = _rubric_breakdown(payload, verdict)

    assert [(row.score, row.earned) for row in breakdown] == [(80, 80)]


def test_hicbir_satir_eslesmezse_kirilim_yok_sayilir() -> None:
    """Farklı adlandırma, kısmi kırılım değildir: cevap 0'a düşürülmez."""
    payload = _payload(("Adımları açıkla", 60), ("Sonucu yaz", 40))
    verdict = _verdict(("Genel değerlendirme", 90))

    assert _rubric_breakdown(payload, verdict) == []


def test_kismi_kirilimda_eksik_olcut_sifir_kalir() -> None:
    """Belgelenmiş fail-closed davranış korunur: cevaplanmamış ölçüt 0 puan."""
    payload = _payload(("Adımları açıkla", 60), ("Sonucu yaz", 40))
    verdict = _verdict(
        ("adımları açıkla", 100),
    )

    breakdown = _rubric_breakdown(payload, verdict)

    assert [(row.point, row.score, row.earned) for row in breakdown] == [
        ("Adımları açıkla", 100, 60),
        ("Sonucu yaz", 0, 0),
    ]


def test_katlanınca_ayni_olan_iki_olcut_gecersiz_sayilir() -> None:
    """ "Adım" ile "ADIM" katlanınca aynıdır; rubrik benzersizliği fold ile ölçülür."""
    chunk_id = uuid4()
    rubric = [RubricItem(point="Adım", weight=50), RubricItem(point="ADIM", weight=50)]
    claim = GroundedCriterionEvidence(criterion="Adım", chunk_id=chunk_id, quote="kaynak")
    breakdown = [RubricCriterionScore(point="Adım", weight=50, score=0, earned=0)]

    assert (
        grounded_criterion_is_valid(
            claim, rubric=rubric, breakdown=breakdown, source_text="kaynak metni"
        )
        is False
    )
