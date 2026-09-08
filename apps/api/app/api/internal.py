"""Dahili uçlar — yalnız altyapı çağırır, kullanıcı arayüzü çağırmaz (T049).

Router `main.py`'ye ZATEN kayıtlıdır ve `include_in_schema=False` taşır: bu uç
istemci sözleşmesinin parçası değildir, OpenAPI'ye girmez ve frontend onu hiç
görmez.

## Tetik ile sürekli işleyicinin ayrımı

Yükleme yanıtından sonra trigger_drain(), Settings.worker_drain_url tanımlıysa
korumalı POST /internal/drain ucunu çağırır; tanımsızsa API sürecinde bir drain
turu çalıştırır. HTTP çağrısının hedefi bu router'ı sunan bir Uvicorn servisidir.
python -m app.worker HTTP portu açmaz ve WORKER_DRAIN_URL hedefi olamaz.

Yerel Compose API'nin HTTP worker tetiğini korur; ayrı worker-poller aynı imajda
python -m app.worker çalıştırarak kuyruk yoklaması ve dönemsel kota bakımını
sağlar. İki tüketici aynı kısa claim/lease/token/revision korumasını kullanır.
Tek HTTP drain çağrısı sürekli bakım takvimi değildir. Scale-to-zero'da durmuş
sürecin uyanışı ayrı barındırma veya zamanlayıcı yapılandırması gerektirir;
yerel süreç kabulü böyle bir canlı uyanışın kanıtı değildir.

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

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep
from app.api.evaluation_runtime import authorize_evaluation, runtime_manifest
from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)
logger = get_logger("app.internal")

#: Worker drain adresinin bağlandığı ortam değişkeninin adı. TANIMSIZSA tetik
#: süreç içi kalır.
#:
#: Değer artık `Settings.worker_drain_url` üzerinden okunur, `os.environ`
#: üzerinden DEĞİL. Sebebi ölçüldü: `pydantic-settings` `.env` dosyasını
#: `Settings`'e okur ama `os.environ`'a YAZMAZ. Doğrudan ortamı okuyan eski
#: satır, `.env` ile yapılandırılmış her dağıtımda değeri bulamıyor ve HER ZAMAN
#: süreç içi dala düşüyordu — yani `docs/deployment.md`'nin ve `.env.example`'ın
#: vaat ettiği uzak worker yolu o biçimde hiç çalışmıyordu. Yalnız gerçek süreç
#: ortamı (docker-compose) doğru davranıyordu. Sabit yalnız değişkenin ADI için
#: durur; testler de bu adı kullanır.
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
    settings = get_settings()
    url = (settings.worker_drain_url or "").strip()
    if not url:
        from app import worker

        try:
            await worker.drain()
        except Exception:
            # İş kuyrukta kalır; bir sonraki tetik veya döngü onu alır.
            logger.warning("worker tetiklenemedi", extra={"context": {"stage": "local_drain"}})
        return

    secret = settings.worker_drain_secret
    if not secret:
        # Uzak uç sırsız zaten 404 döner; boşuna istek atmak yerine sebebi yazarız.
        logger.error(
            "worker URL'i tanımlı ama WORKER_DRAIN_SECRET yok — uzak drain ucu kapalı",
            extra={"context": {"stage": "remote_drain_configuration"}},
        )
        return

    try:
        async with httpx.AsyncClient(timeout=TRIGGER_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers={"X-Worker-Secret": secret})
        response.raise_for_status()
        logger.info(
            "uzak worker tetiklendi",
            extra={"context": {"status": response.status_code}},
        )
    except Exception:
        logger.warning("uzak worker tetiklenemedi", extra={"context": {"stage": "remote_drain"}})


@router.get("/evaluation/runtime")
async def evaluation_runtime(
    run_id: UUID,
    request: Request,
    settings: SettingsDep,
) -> dict[str, object]:
    """Return this isolated runtime's secret-free configuration receipt."""
    return runtime_manifest(authorize_evaluation(request, settings), run_id)
