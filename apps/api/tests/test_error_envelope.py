"""Hata zarfı tek sözleşme — 002 lider turu (T406 backend yarısı).

Sözleşme: `{"error": {"code", "message", "request_id"}}`.

Neden lider turunda sabitlendi: zarfı backend bir şerit, istemci tarafını başka
bir şerit yazacak. İkisi ayrı ayrı yazsaydı bu depoda bir kez olan şey tekrar
olurdu — `chat.py` ile `schemas/chat.py` iki ayrı zarf tanımlamıştı ve iki taraf
ayrıştığında **her istek 422 dönüyordu**; ikisinin de testleri kendi kopyasına
karşı yeşildi. Sözleşmeyi önce sabitlemek, o hatanın yapısal karşılığıdır.

`request_id`'nin ayrı bir önemi var: destek kodu olarak kullanıcıya gösterilecek.
"Bazen var" bir alan, istemcide "bazen göster" demektir; kullanıcıya kod vaat edip
vermemek hiç vermemekten kötüdür. Bu yüzden alan zorunlu ve handler'ın son çaresi
kimliği üretmektir.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    AppError,
    app_error_handler,
    error_response,
    request_id_of,
    unhandled_error_handler,
    validation_error_handler,
)
from tests.conftest import UserFactory


def _assert_envelope(body: dict[str, Any]) -> dict[str, Any]:
    """Zarfın şeklini tek yerde doğrular; üç handler da aynı şekli üretmeli."""
    assert set(body) == {"error"}, f"zarfın kökü yalnız 'error' olmalı: {body}"
    error = body["error"]
    assert set(error) == {"code", "message", "request_id"}, f"alan kümesi değişmiş: {error}"
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["request_id"], str) and error["request_id"]
    return error


class TestUcHandlerAyniZarfiUretir:
    async def test_app_error_zarfi(self, client: AsyncClient, users: UserFactory) -> None:
        """AppError yolu: üye olunmayan ders 404 döner."""
        user_id = await users.create("zarf-app@dogus.edu.tr")

        response = await client.get(f"/courses/{uuid4()}/documents", headers=users.auth(user_id))

        assert response.status_code == 404, response.text
        error = _assert_envelope(response.json())
        assert error["code"] == "not_found"

    async def test_validation_error_zarfi(self, client: AsyncClient, users: UserFactory) -> None:
        """Doğrulama yolu: FastAPI'nin İngilizce `detail` biçimi sızmamalı."""
        user_id = await users.create("zarf-val@dogus.edu.tr")

        response = await client.post("/courses", json={"code": "X"}, headers=users.auth(user_id))

        assert response.status_code == 422, response.text
        error = _assert_envelope(response.json())
        assert error["code"] == "validation_error"
        assert "detail" not in response.json()

    async def test_unhandled_error_zarfi(self) -> None:
        """Beklenmeyen hata yolu.

        Kendi mini uygulaması kuruluyor: gerçek uygulamaya "her zaman patlayan"
        bir uç eklemek, üretim sözleşmesine yalnız test için bir yol açmak
        olurdu.
        """
        app = FastAPI()
        app.add_exception_handler(AppError, app_error_handler)
        app.add_exception_handler(RequestValidationError, validation_error_handler)
        app.add_exception_handler(Exception, unhandled_error_handler)

        @app.get("/patla")
        async def patla() -> None:
            raise RuntimeError("bilerek")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.get("/patla")

        assert response.status_code == 500
        error = _assert_envelope(response.json())
        assert error["code"] == "internal_error"
        assert "bilerek" not in error["message"], "ham istisna metni kullanıcıya gitmemeli"
        assert "RuntimeError" not in error["message"]


class TestRequestId:
    async def test_gonderilen_kimlik_zarfa_ve_basliga_yansir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İstemci kimliği verirse sunucu onu korur: uçtan uca izleme bunu ister."""
        user_id = await users.create("zarf-rid@dogus.edu.tr")
        headers = {**users.auth(user_id), "X-Request-ID": "izlenebilir-kimlik-42"}

        response = await client.get(f"/courses/{uuid4()}/documents", headers=headers)

        assert response.json()["error"]["request_id"] == "izlenebilir-kimlik-42"
        assert response.headers["X-Request-ID"] == "izlenebilir-kimlik-42"

    async def test_kimlik_verilmezse_uretilir_ve_basligla_ayni_olur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Gövdedeki kod ile logdaki kayıt aynı olmalı; ayrışırsa destek kodu işe yaramaz."""
        user_id = await users.create("zarf-rid2@dogus.edu.tr")

        response = await client.get(f"/courses/{uuid4()}/documents", headers=users.auth(user_id))

        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]

    def test_middleware_gecilmese_de_kimlik_bos_kalmaz(self) -> None:
        """Son çare: `request.state` boşsa handler kimliği kendisi üretir.

        Bu dal fail-closed bir varsayılan. Boş bırakılsaydı zarf bazen üç bazen
        iki alanlı olurdu ve istemci "alan varsa göster" diye yazılırdı — yani
        kullanıcı bazen destek kodu görürdü, bazen görmezdi.
        """
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

        first = request_id_of(request)
        second = request_id_of(request)

        assert first and second
        assert first != second, "state yokken her çağrı taze kimlik üretmeli"

    def test_error_response_zarfi_kurar(self) -> None:
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

        response = error_response(request, status_code=418, code="demlik", message="Ben demliğim.")

        assert response.status_code == 418


class TestBlueprintRouter:
    """Blueprint router'ı `main.py`'ye lider turunda kaydedildi ve orada kaldı.

    Testin ilk hâli "router kayıtlı ama boş" diyordu ve yolu 26'da sabitliyordu;
    o beklenti blueprint şeridi başlayana kadar geçerliydi. Şerit T504'ü kapatınca
    beklenti **silinmedi, güncellendi**: sabitlenen şey sayının kendisi değil,
    `main.py`'ye dokunulmamış olmasıdır — prefix hâlâ liderin koyduğu prefix ve
    yollar yalnız bu router'ın gövdesinden geliyor.
    """

    def test_router_liderin_prefixinde_kalir(self) -> None:
        from app.api import blueprints

        assert blueprints.router.prefix == "/courses/{course_id}"

    def test_yol_sayisi_blueprint_uclariyla_buyudu(self) -> None:
        from app.main import create_app

        app = create_app()
        yollar = set(app.openapi()["paths"])
        blueprint_yollari = {
            yol for yol in yollar if "blueprint" in yol or "learning-outcome" in yol
        }

        assert len(blueprint_yollari) == 7, f"blueprint yolları: {sorted(blueprint_yollari)}"
        assert len(yollar) == 40, f"yol sayısı değişmiş: {len(yollar)}"


class TestAyarAdlari:
    """T203/T205'in ayar adları lider turunda sabitlendi.

    İki şerit aynı ayara iki farklı ad verirse, ikisi de kendi adıyla çalışan ama
    birbirini görmeyen kod yazar. `.env.example` ile `Settings` eşleşmesini
    `test_config.py` ayrıca tarıyor; burada yalnız adların ve varsayılanların
    var olduğu sabitleniyor.
    """

    @pytest.mark.parametrize(
        ("alan", "beklenen"),
        [
            ("question_gen_rate_limit_requests", 5),
            ("question_gen_rate_limit_window_seconds", 300.0),
            ("question_gen_max_concurrent", 1),
            ("embedding_warmup_enabled", True),
        ],
    )
    def test_alan_ve_varsayilan(self, alan: str, beklenen: object) -> None:
        from app.core.config import Settings

        assert alan in Settings.model_fields, f"{alan} lider sözleşmesinde vardı"
        assert getattr(Settings(_env_file=None), alan) == beklenen  # type: ignore[call-arg]

    def test_soru_uretimi_siniri_sohbetin_kopyasi_degil(self) -> None:
        """Kopya olsaydı dakikada 400 soru üretimi tetiklenebilirdi.

        Tek çağrı 20 soruya kadar üretiyor ve her soru ayrı bir LLM turu; maliyet
        profili sohbetten bir büyüklük mertebesi farklı.
        """
        from app.core.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.question_gen_rate_limit_requests < settings.chat_rate_limit_requests
        assert (
            settings.question_gen_rate_limit_window_seconds
            > settings.chat_rate_limit_window_seconds
        )
