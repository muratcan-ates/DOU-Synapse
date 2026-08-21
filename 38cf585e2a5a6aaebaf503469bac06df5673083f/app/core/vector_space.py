"""Vektör uzayının kimliği — "bu embedding hangi dünyada üretildi".

Bu modül 9 Ağustos akşamı liderin R4'e devrettiği açık riski kapatmak için var
(`14_R4_KALITE.md`, EK). Risk şu:

    The model intfloat/multilingual-e5-large now uses mean pooling instead of
    CLS embedding. In order to preserve the previous behaviour, consider either
    pinning fastembed version to 0.5.1 ...

Bu bir kullanımdan kaldırma uyarısı değil, **vektör uzayı değişikliğidir.** Bir
korpus bir havuzlama stratejisiyle embed edilip başka biriyle sorgulanırsa sessizce
yanlış komşular döner: çökme yok, istisna yok, yalnız retrieval kötüleşir. Aynı gün
bunun kardeşi canlıda görüldü — dev korpusu `hashing` ile ingest edilmişti, sorgular
`fastembed` uzayındaydı, ve sonuç saatlerce "retrieval kötü" diye okundu.

## Uzayı ne tanımlar

Üç bileşen ve **üçü de gerekli**:

* **Sağlayıcı türü** — `fastembed` ile `hashing` bambaşka uzaylar; biri anlamsal,
  diğeri sözcük karması.
* **Model adı** — `multilingual-e5-large` ile `bge-m3` aynı boyutu üretse bile
  aynı uzay değildir. (Boyut eşitliği bu yüzden bir kontrol olarak YETMEZ; şema
  `vector(1024)` diyor ve iki model de oraya sığıyor.)
* **Kütüphane sürümü** — yukarıdaki uyarının konusu. Aynı sağlayıcı, aynı model,
  farklı sürüm → farklı vektörler. Kimliğin en kolay unutulan parçası bu ve tam da
  bu yüzden burada açıkça duruyor.

## Neden tek bir dize

Üç ayrı sütun ölçüm ve raporlama için daha rahat olurdu, ama karşılaştırma üç kez
yapılırdı ve üçüncüsü bir gün unutulurdu. Tek kanonik dize, uyuşmazlık kontrolünü
tek bir `!=` yapar; ayrıştırma gerektiğinde biçim belgelenmiş ve ayrılabilir:

    <sağlayıcı>/<model>@<sürüm>

    fastembed/intfloat/multilingual-e5-large@0.8.0
    hashing/hashing-v1@builtin-1

Model adının kendisi eğik çizgi içeriyor; bu yüzden ayrıştırırken **ilk** eğik
çizgiden ve **son** `@`'ten bölünür.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from app.modules.ingestion.embedding import (
    FastEmbedProvider,
    HashingEmbeddingProvider,
    get_embedding_provider,
)

#: Karma sağlayıcının "sürümü" bir paket sürümü değil, ALGORİTMANIN sürümüdür.
#: `HashingEmbeddingProvider._embed` değişirse (hash fonksiyonu, işaret kuralı,
#: normalizasyon) bu sabit ELLE artırılmalıdır — yoksa eski vektörler yeni
#: vektörlerle aynı uzayda sayılır ve uyuşmazlık kontrolü sessizce yalan söyler.
HASHING_ALGORITHM_VERSION = "builtin-1"

#: Kütüphane sürümü okunamadığında kullanılan işaret. Kanonik dizeye girer ve
#: dolayısıyla "sürümü bilinmeyen uzay" başka hiçbir uzaya eşit olmaz — bilinmezlik
#: eşitlik varsaymaktan iyidir (fail-closed).
UNKNOWN_VERSION = "bilinmiyor"


def _library_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:  # pragma: no cover - kurulu olmayan ortam
        return UNKNOWN_VERSION


def space_of(provider: object) -> str:
    """Verilen sağlayıcının kanonik uzay kimliği.

    `isinstance` ile ayrım bilinçli: `EmbeddingProvider` protokolünde uzay kimliği
    yok ve protokol `app/modules/ingestion/` altında, bu şeridin dosyası değil.
    Protokole bir `space` özelliği eklemek daha temiz olurdu ve gruba önerildi;
    o inene kadar eşleme burada, tek yerde duruyor.

    Tanınmayan bir sağlayıcı için sınıf adı kullanılır: uydurma bir kimlik
    üretmektense tanınabilir ama farklı bir kimlik üretmek — o sağlayıcıyla
    yazılmış chunk'lar, başka hiçbir uzayla eşleşmez.
    """
    if isinstance(provider, FastEmbedProvider):
        return f"fastembed/{provider.name}@{_library_version('fastembed')}"
    if isinstance(provider, HashingEmbeddingProvider):
        return f"hashing/{provider.name}@{HASHING_ALGORITHM_VERSION}"
    name = getattr(provider, "name", type(provider).__name__)
    return f"{type(provider).__name__}/{name}@{UNKNOWN_VERSION}"


def current_space() -> str:
    """Bu süreçte yapılandırılmış sağlayıcının uzayı.

    Hem ingest (damgayı yazan) hem sorgu (damgayı denetleyen) tarafı bu
    fonksiyonu çağırır. İki taraf ayrı hesaplasaydı, ayrışmaları an meselesiydi —
    ve ayrışma tam olarak bu modülün önlemek için var olduğu hata sınıfı.
    """
    return space_of(get_embedding_provider())


__all__ = [
    "HASHING_ALGORITHM_VERSION",
    "UNKNOWN_VERSION",
    "current_space",
    "space_of",
]
