"""Sınav cevaplarını tek bir toplam puana katlama kuralları."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID


class ScorableOutcome(Protocol):
    """Toplam puanın ihtiyaç duyduğu en dar cevap sonucu sözleşmesi."""

    graded: bool
    score: int | None


def score_of(
    outcomes: Mapping[UUID, ScorableOutcome],
    weights: Mapping[UUID, int] | None = None,
) -> float | None:
    """Cevaplanmış ve değerlendirilmiş sonuçların puanını hesapla.

    ``outcomes`` soru kimliğiyle anahtarlanır; bu nedenle cevap sırası puanı
    etkileyemez. ``graded=False`` veya ``score=None`` sonuçlar mevcut sözleşme
    gereği hem paydan hem de paydadan çıkar. Cevaplanmamış sorular bu eşlemede
    bulunmaz ve onlar da yanlış sayılmaz.

    ``weights=None`` legacy/self-servis akışıdır ve eşit ortalamayı korur.
    Blueprint akışında her dahil edilen sonucun aynı ``question_id`` için
    pozitif tam sayı ağırlığı bulunmalıdır. Eksik, bool, tam sayı olmayan,
    sıfır veya negatif ağırlık ``ValueError`` üretir; puan tahmin edilmez.
    Ağırlık eşlemesindeki cevapsız sorular fazladan bulunabilir.

    Hiç dahil edilebilir sonuç yoksa iki akışta da ``None`` döner.
    """
    included: list[tuple[UUID, int]] = []
    for question_id, outcome in outcomes.items():
        score = outcome.score
        if outcome.graded and score is not None:
            included.append((question_id, score))
    if not included:
        return None

    if weights is None:
        return round(sum(score for _, score in included) / len(included), 1)

    weighted_total = 0
    total_weight = 0
    for question_id, score in included:
        try:
            weight = weights[question_id]
        except KeyError as exc:
            raise ValueError(f"Değerlendirilmiş soru için ağırlık eksik: {question_id}") from exc
        if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
            raise ValueError(f"Soru ağırlığı pozitif tam sayı olmalıdır: {question_id}")

        weighted_total += score * weight
        total_weight += weight

    return round(weighted_total / total_weight, 1)
