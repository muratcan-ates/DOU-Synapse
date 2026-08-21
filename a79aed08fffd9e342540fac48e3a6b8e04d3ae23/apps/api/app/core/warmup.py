"""Embedding modelinin başlangıçta ısıtılması (FR-221).

## Neden `yield`'den önce `await` EDİLMİYOR

Isıtma, üretim sağlayıcısında modelin diskten belleğe alınması demek. 001'in
ölçümlerinde ilk soru 11,7 sn, ilk yükleme 19,1 sn sürüyordu; bu cezayı
başlangıca taşımak kullanıcıdan almak anlamına gelir. Ama başlangıcı BEKLETMEK
yeni ve daha büyük bir arıza üretirdi: 19 sn'lik bir startup, ACA'nın startup
probe penceresini ve Compose'un healthcheck retry'ını aşar, konteyner sağlıklı
olduğu hâlde öldürülür ve süreç sonsuz yeniden başlatma döngüsüne girer.

Bu yüzden ısıtma bir **arka plan görevi**dir ve `lifespan` onu beklemez.
"Süreç ayakta mı" ile "embedding hazır mı" ayrı sorular: birincisini
`/health/live` (bağımlılıksız) yanıtlar, ikincisi `/health/ready`'nin `checks`
sözlüğüne bir bağımlılık durumu olarak girer.

## Durumların anlamı

* `disabled` — bu süreçte ısıtma çalışmıyor. Ya operatör kapattı
  (`EMBEDDING_WARMUP_ENABLED=false`) ya da `lifespan` hiç koşmadı (testler
  uygulamayı `ASGITransport` ile sürüyor ve httpx lifespan olayı göndermez).
  Hazırlığı DÜŞÜRMEZ: model ilk istekte tembel yüklenir, yani bu, ısıtma
  eklenmeden önceki davranıştır ve çalışır durumdur.
* `warming` — görev koşuyor. Hazırlığı düşürür (503): orkestratör ısınma
  bitmeden trafiği buraya yöneltmemeli, yoksa ilk kullanıcı soğuk başlangıç
  cezasını yine tek başına öder.
* `ok` — model yüklendi.
* `failed` — ısıtma patladı (fastembed import hatası, model dizini eksik).
  Hazırlığı düşürür. Bu bilinçli bir fail-closed seçim (Anayasa IV) ve bedeli
  var: FTS şeridi embedding olmadan da çalıştığından süreç "yarı çalışır"
  durumda trafikten çekilir. Alternatif — 200 dönüp sessizce bozuk retrieval
  servis etmek — bu depoda adı konmuş en kötü hata sınıfı: kullanıcının
  yanlışlığını anlayamayacağı hata.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.ingestion.embedding import get_embedding_provider

logger = get_logger("app.warmup")

WarmupState = Literal["disabled", "warming", "ok", "failed"]

# Isıtma kapalıyken model ilk istekte tembel yüklenebilir; bu nedenle `disabled`
# hazırlığı düşürmez. `warming` ve `failed` ise trafiğin bu sürece
# yönlendirilmemesi gereken iki durumdur. Health ve admin konsolu aynı gerçeği
# göstersin diye karar tek yerde tutulur.
_READY_STATES = frozenset({"ok", "disabled"})

#: Isıtma sırasında sağlayıcıya verilen metin. İçeriği önemsiz; amaç modelin
#: yüklenmesini tetiklemek.
WARMUP_QUERY = "ısınma"

_state: WarmupState = "disabled"


def warmup_state() -> WarmupState:
    """Bu süreçteki ısıtma durumu. `/health/ready` bunu raporlar."""
    return _state


def warmup_is_ready(state: WarmupState | None = None) -> bool:
    """Verilen (veya güncel) ısıtma durumunun trafiğe hazır olup olmadığı."""
    return (warmup_state() if state is None else state) in _READY_STATES


def reset_warmup_state() -> None:
    """Testler için durum sıfırlama."""
    global _state
    _state = "disabled"


async def warm_embedding() -> None:
    """Sağlayıcıyı bir kez çağırıp modeli belleğe aldırır.

    Çağrı `to_thread` ile sarılı çünkü senkron ve CPU'ya bağlı — sarılmasaydı
    ısıtma, tam da önlemek için var olduğu şeyi yapar ve başlangıçtan hemen
    sonraki istekleri bloke ederdi (FR-220 ile aynı karar).

    Hata YUTULUR ve duruma yazılır: ısıtma bir kolaylık katmanıdır, patlaması
    sürecin ölmesi için sebep değil. Sonucu okuyan yer `/health/ready`.
    """
    global _state
    _state = "warming"
    try:
        await asyncio.to_thread(get_embedding_provider().embed_query, WARMUP_QUERY)
    except asyncio.CancelledError:
        # Kapanış sırasında iptal edildi; bu bir arıza değil.
        raise
    except Exception:
        _state = "failed"
        logger.exception("embedding ısıtması başarısız")
    else:
        _state = "ok"
        logger.info("embedding ısıtması tamamlandı")


def start_warmup() -> asyncio.Task[None] | None:
    """Isıtmayı arka planda başlatır; kapalıysa `None` döner.

    Durum görev koşmaya başlamadan ÖNCE, senkron olarak `warming`'e çekilir:
    `create_task` coroutine'i hemen çalıştırmaz ve arada gelen bir hazırlık
    yoklaması, ısıtma başlamışken `disabled` okurdu.
    """
    global _state
    if not get_settings().embedding_warmup_enabled:
        _state = "disabled"
        logger.info("embedding ısıtması kapalı")
        return None
    _state = "warming"
    return asyncio.create_task(warm_embedding())


__all__ = [
    "WARMUP_QUERY",
    "WarmupState",
    "reset_warmup_state",
    "start_warmup",
    "warm_embedding",
    "warmup_is_ready",
    "warmup_state",
]
