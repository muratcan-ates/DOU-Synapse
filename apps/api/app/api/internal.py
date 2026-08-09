"""Dahili uçlar — yalnız altyapı çağırır, kullanıcı arayüzü çağırmaz (T049).

Router `main.py`'ye ZATEN kayıtlıdır ve `include_in_schema=False` taşır: bu uç
istemci sözleşmesinin parçası değildir, OpenAPI'ye girmez ve frontend onu hiç
görmez.

## Neden bir HTTP tetiği

Bugün yükleme ucu, yanıt gönderildikten sonra süreç içinde `worker.drain()`
koşturuyor. Bu yalnız API ve worker AYNI süreçte olduğunda çalışır. ACA
kararında (tasks.md T049) tek imaj iki ayrı Container App olarak koşuyor:
`api` uvicorn'u, `worker` ise `python -m app.worker`'ı çalıştırıyor ve
scale-to-zero ile uyuyor. Uyuyan worker'ı uyandırmanın yolu ona bir HTTP isteği
göndermektir; kuyruğu yoklayan bir döngü scale-to-zero'yu anlamsızlaştırırdı.

## Neden sırla korunuyor ve sırsızken hiç açılmıyor

`drain()` iş kuyruğunu boşaltır: dışarıdan tetiklenebilen korumasız bir uç,
kimliği olmayan birinin embedding üretimini istediği kadar çalıştırmasına izin
verirdi (para ve CPU). Sır tanımsızken uç 404 döner — 403 değil: 403, "burada
korunan bir uç var" bilgisini sızdırır ve sırrı aramaya davet eder. Fail-closed
kural (Anayasa IV) yapılandırılmamış bir korumayı açık bırakmaz.

Uç **kullanıcı kimliği istemez** (bir insan ucu değildir, `CourseMemberDep`
kullanmaz) ama paylaşılan sırrı ister.
"""

from __future__ import annotations

import os
from secrets import compare_digest
from typing import Annotated

import httpx
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep
from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)
logger = get_logger("app.internal")

#: Worker servisinin drain ucunun tam adresi. TANIMSIZSA tetik süreç içi kalır.
#:
#: Neden `Settings` alanı değil ortam değişkeni: `core/config.py` bu fazda beş
#: oturuma kapalıdır (10_OKU_ONCE_FAZ2 §3) ve içinde yalnız `worker_drain_secret`
#: önden açılmıştı. Değişkenin `Settings.worker_drain_url` alanına taşınması
#: raporda lidere iletildi; taşındığında burası tek satırda değişir.
WORKER_DRAIN_URL_ENV = "WORKER_DRAIN_URL"

#: Tetik çağrısının zaman aşımı. Kısa tutulur: bu çağrı yükleme yanıtı istemciye
#: gittikten SONRA arka planda koşar, ama asılı kalan bir bağlantı worker
#: ölçeklenirken istek işleyicisini boşuna meşgul eder. Worker'ı uyandırmak
#: yeterlidir; işin bitmesini beklemek gerekmez.
TRIGGER_TIMEOUT_SECONDS = 10.0


class DrainOut(BaseModel):
    """Bir turda işlenen iş sayısı."""

    processed: int = Field(description="Bu turda işlenen ingestion işi sayısı")


@router.post("/drain", response_model=DrainOut)
async def drain_jobs(
    settings: SettingsDep,
    x_worker_secret: Annotated[str | None, Header(alias="X-Worker-Secret")] = None,
) -> DrainOut:
    """Bekleyen ingestion işlerini bir tur işler.

    Kimlik doğrulaması istemez, paylaşılan sır ister. Sır tanımlı değilse uç
    yokmuş gibi davranır (404).
    """
    expected = settings.worker_drain_secret
    if not expected:
        # Yapılandırılmamış koruma = kapalı uç. Log'a sır yazılmaz.
        logger.warning("drain ucu çağrıldı ama WORKER_DRAIN_SECRET tanımsız — 404 dönüldü")
        raise NotFoundError("Bulunamadı.")

    # Sabit zamanlı karşılaştırma: düz `==` ilk farklı bayta kadar karşılaştırıp
    # döner, yani cevap süresi doğru önekin uzunluğuyla ilişkilidir ve sır bayt
    # bayt tahmin edilebilir hâle gelir. `compare_digest` bu ilişkiyi keser.
    supplied = x_worker_secret or ""
    if not compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        logger.warning("drain ucuna yanlış sırla erişim denendi")
        raise PermissionDeniedError("Bu işlem için yetkiniz yok.")

    from app import worker

    processed = await worker.drain()
    logger.info("drain tamamlandı", extra={"context": {"processed": processed}})
    return DrainOut(processed=processed)


async def trigger_drain() -> None:
    """Worker'ı bir tur çalıştırır: uzak servis varsa HTTP ile, yoksa süreç içi.

    `documents.py::_trigger_worker` bunu çağırır ve çağıran kod her iki dağıtım
    biçiminde aynı kalır (ARCHITECTURE.md §1'in vaadi).

    Hata YUTULUR ve loglanır: iş `ingestion_jobs` tablosunda bekliyor, bir
    sonraki tetik ya da worker döngüsü onu alır. Tetiğin başarısızlığı yükleme
    isteğini başarısız saymaz — dosya kaydedilmiştir.
    """
    url = os.environ.get(WORKER_DRAIN_URL_ENV, "").strip()
    if not url:
        from app import worker

        try:
            await worker.drain()
        except Exception:
            # İş kuyrukta kalır; bir sonraki tetik veya döngü onu alır.
            logger.exception("worker tetiklenemedi")
        return

    secret = get_settings().worker_drain_secret
    if not secret:
        # Uzak uç sırsız zaten 404 döner; boşuna istek atmak yerine sebebi yazarız.
        logger.error(
            "worker URL'i tanımlı ama WORKER_DRAIN_SECRET yok — uzak drain ucu kapalı",
            extra={"context": {"url": url}},
        )
        return

    try:
        async with httpx.AsyncClient(timeout=TRIGGER_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers={"X-Worker-Secret": secret})
        response.raise_for_status()
        logger.info(
            "uzak worker tetiklendi",
            extra={"context": {"url": url, "status": response.status_code}},
        )
    except Exception:
        logger.exception("uzak worker tetiklenemedi", extra={"context": {"url": url}})
