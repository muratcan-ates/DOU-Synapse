"""Reciprocal Rank Fusion — iki sıralamayı skorlarını kalibre etmeden birleştirir.

Neden RRF: dense arama kosinüs benzerliği (mutlak, [-1, 1]) üretir, FTS ise `ts_rank`
(sorgunun terim sayısına ve belge uzunluğuna bağlı, sorgular arasında karşılaştırılamaz)
üretir. Bu ikisini ağırlıklı toplamak için önce ortak bir ölçeğe oturtmak gerekirdi ve
o kalibrasyonu yapacak veri elimizde yok. RRF yalnızca **sıraya** bakar; ölçek sorunu
tanım gereği ortadan kalkar (ARCHITECTURE.md §1, Füzyon satırı).

Formül::

    score(d) = Σ_i  1 / (k + rank_i(d))          rank 1'den başlar

`k` büyüdükçe üst sıralar arasındaki fark yumuşar; k=60 literatürdeki standart
başlangıçtır ve `config.retrieval_rrf_k` üzerinden değiştirilebilir.

**Bu skor mutlak bir anlam taşımaz.** Üst sınırı yalnızca sıralama sayısına bağlıdır
(n sıralama için n/(k+1)) ve tamamen alakasız bir korpus da aynı üst sınırı üretir:
her sıralamanın bir birincisi vardır. Bu yüzden kanıt eşiği fused skora uygulanamaz —
gerekçe ve alternatif için `service.py`.

Modül saf tutuldu: veritabanı, ayar ya da contracts bağımlılığı yoktur, dolayısıyla
formül gerçek embedding indirmeden sentetik sıralamalarla test edilebilir (T007/2).
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion[Key: Hashable](
    rankings: Sequence[Sequence[Key]], *, k: int = DEFAULT_RRF_K
) -> list[tuple[Key, float]]:
    """Sıralamaları birleştirip (anahtar, skor) çiftlerini azalan skorla döndürür.

    `rankings` her biri en iyiden en kötüye sıralı anahtar dizileridir. Bir anahtarın
    aynı sıralamada iki kez geçmesi çift sayıma yol açacağı için ilk geçişi esas alınır;
    SQL tarafı zaten tekil satır döndürür, bu yalnızca saf fonksiyonun kendini koruması.

    Beraberlik bozma sırası **belirlenimcidir**: önce skor, sonra en iyi (küçük) sıra,
    sonra ilk görülme sırası. Rastgele sıralama, aynı sorgunun iki koşumda farklı cevap
    üretmesi demek olurdu; kalibrasyon ve regresyon testleri bunun üzerine kurulamaz.
    """
    if k < 0:
        raise ValueError("RRF sabiti k negatif olamaz.")

    scores: dict[Key, float] = {}
    best_rank: dict[Key, int] = {}
    first_seen: dict[Key, int] = {}

    for ranking in rankings:
        seen: set[Key] = set()
        for rank, key in enumerate(ranking, start=1):
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key in best_rank:
                best_rank[key] = min(best_rank[key], rank)
            else:
                best_rank[key] = rank
                first_seen[key] = len(first_seen)

    return sorted(
        scores.items(),
        key=lambda item: (-item[1], best_rank[item[0]], first_seen[item[0]]),
    )


def max_possible_score(ranking_count: int, *, k: int = DEFAULT_RRF_K) -> float:
    """Verilen sıralama sayısı için erişilebilir en yüksek fused skor.

    Testler ve kalibrasyon için: bu değerin sorgunun kalitesinden bağımsız olduğunu
    göstermek, fused skorun neden eşik olarak kullanılamayacağının kanıtıdır.
    """
    return ranking_count * (1.0 / (k + 1))
