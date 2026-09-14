"""JWT doğrulamasının NEGATİF testleri — HTTP yüzeyinden (FAZ F / F1).

`tests/test_security.py` `authenticate()` fonksiyonunu doğrudan çağırır ve yalnız
`AuthenticationError` yükseldiğini görür. Bu dosya bir katman yukarıda durur:
bozuk token gerçek bir uç noktaya gönderilir ve **HTTP durum kodu ile hata
zarfındaki `error.code` birlikte** doğrulanır. Aradaki fark önemsiz değil — bir
dizi `raise` doğru ama `app_error_handler` kaydı ya da zarf sözleşmesi bozulmuş
olsaydı, fonksiyon testleri yeşil yanmaya devam ederken istemci 401 yerine 500
görürdü ve oturumu yenilemek yerine "İşlem tamamlanamadı" derdi.

Sınanan dokuz vaka (runbook FAZ F):
1. sahte imza (yapı doğru, anahtar yanlış), 2. süresi dolmuş token,
3. yanlış issuer, 4. yanlış audience, 5. `alg: none` ile imzasız token,
6. imza bölümü tamamen çıkarılmış token, 7. HS256 dışı algoritma (HS512),
8. `Bearer` öneki eksik/bozuk `Authorization` başlığı, 9. geçersiz base64 gövde.

Kontrollerin kendisi `app/core/config.py` ve `app/core/security.py`'de zaten
vardı; eksik olan kanıttı. Bu paket koşturulduğunda dokuzunun da gerçekten
kapandığı ölçüldü ve `security.py`'de açık bulunmadı, dolayısıyla kaynak
dosyaya dokunulmadı.

İki pozitif kontrol bilinçli olarak burada: geçerli bir token'ın 200 dönmesi ve
küçük harfli `bearer` şemasının kabul edilmesi. Onlar olmadan dokuz testin
tamamı, kimlik doğrulaması tümüyle kırık bir uygulamada da yeşil yanardı.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.security import MESSAGE_INVALID_SESSION
from tests.conftest import UserFactory

# Aşağıdaki iki dize TEST ANAHTARIDIR: yalnız bu dosyadaki token'ları imzalamak için
# üretilmiştir, hiçbir ortamda kullanılmaz ve gerçek bir Supabase secret'ının değeri
# DEĞİLDİR. Uzunlukları bilinçli: HS256 için 32 bayttan kısa anahtar PyJWT'de uyarı
# üretir ve testin ölçtüğü şeyin yanına gürültü koyar.
TEST_SECRET = "dou-synapse-negatif-test-anahtari-32-bayttan-uzun"
OTHER_PROJECT_TEST_SECRET = "baska-projenin-negatif-test-anahtari-uzun"

ISSUER = "https://proje.supabase.co/auth/v1"
AUDIENCE = "authenticated"

#: Kimlik isteyen, gövdesiz ve yan etkisiz uç. Kimlik reddi veritabanı oturumu
#: açılmadan önce gerçekleştiği için bozuk token vakaları veriye hiç dokunmaz.
PROTECTED_PATH = "/me/profile"


def _settings() -> Settings:
    """Testin ayarları: imza zorunlu, issuer sabitlenmiş, dev kimliği KAPALI.

    `conftest.py` bütün paket için `DEV_AUTH_ENABLED=true` veriyor ve
    `SUPABASE_JWT_SECRET`'ı ortamdan siliyor. Bu dosyada imza yolunun sınanması
    gerektiği için ikisi de burada tersine çevriliyor; `_env_file=None` ve açık
    değerler, geliştiricinin makinesindeki `.env` dosyasının sonucu değiştirmesini
    de engelliyor.
    """
    return Settings(
        _env_file=None,
        environment="local",
        supabase_jwt_secret=TEST_SECRET,
        dev_auth_enabled=False,
        jwt_issuer=ISSUER,
    )


@pytest.fixture
async def auth_client(clean_tables: None) -> AsyncIterator[AsyncClient]:
    """Gerçek uygulama, yalnız ayarları değiştirilmiş hâlde.

    `create_app()` kullanılıyor: hata zarfını üreten handler kayıtları, middleware
    sırası ve bağımlılık zinciri üretimdekiyle aynı olmalı. Yalnız `get_settings`
    bağımlılığı geçersiz kılınıyor ki imza doğrulaması devrede olsun.
    """
    from app.core.db import dispose_engine
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
    await dispose_engine()


def _b64url(raw: bytes) -> str:
    """JWT'nin dolgusuz base64url kodlaması."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _token(
    secret: str = TEST_SECRET,
    *,
    algorithm: str = "HS256",
    **overrides: Any,
) -> str:
    """Supabase'in ürettiğine biçimsel olarak denk bir token üretir.

    `None` verilen claim tamamen ÇIKARILIR; böylece "eksik claim" vakaları da
    aynı yardımcıyla kurulabilir.
    """
    now = datetime.now(tz=UTC)
    claims: dict[str, Any] = {
        "sub": str(uuid4()),
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "email": "ayse@dogus.edu.tr",
    }
    claims.update(overrides)
    return jwt.encode(
        {key: value for key, value in claims.items() if value is not None},
        secret,
        algorithm=algorithm,
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signed_garbage_payload_token() -> str:
    """Gövdesi base64 OLMAYAN ama imzası o gövdeye göre DOĞRU olan token.

    Rastgele bir dize göndermek yetmez: PyJWT imzayı gövdeyi çözmeden önce
    doğrular, dolayısıyla öylesine bozuk bir token imza adımında elenir ve
    base64 çözümleme yolu hiç sınanmamış olur. Burada imza bilerek tutturuluyor
    ki reddin sebebi gerçekten gövdenin çözülememesi olsun.
    """
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = "{bu-base64-degil}"
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(TEST_SECRET.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def _assert_unauthorized(response: Any) -> dict[str, Any]:
    """401 + hata zarfı sözleşmesi. Yalnız durum kodu bakmak yetmez.

    `error.code` istemcinin oturumu yenileme kararını verdiği alandır; kod
    değişirse arayüz kullanıcıyı giriş ekranına göndermek yerine genel bir hata
    gösterir. Zarfın şekli `tests/test_error_envelope.py` ile aynı sözleşmedir.
    """
    assert response.status_code == 401, response.text
    body = response.json()
    assert set(body) == {"error"}, f"zarfın kökü yalnız 'error' olmalı: {body}"
    error = body["error"]
    assert set(error) == {"code", "message", "request_id"}, f"alan kümesi değişmiş: {error}"
    assert error["code"] == "unauthenticated", error
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["request_id"], str) and error["request_id"]
    return error


def _rejected_tokens() -> dict[str, str]:
    """Dokuz vakanın token taşıyan sekizi; sekizinci vaka başlık düzeyinde ayrı.

    Tek yerde tutuluyor çünkü hem tek tek testler hem de bilgi sızıntısı testi
    aynı listeyi okuyor; iki kopya ayrıştığı gün sızıntı testi eksik kalırdı.
    """
    valid = _token()
    header, payload, _ = valid.split(".")
    return {
        "sahte_imza": _token(OTHER_PROJECT_TEST_SECRET),
        "suresi_dolmus": _token(exp=datetime.now(tz=UTC) - timedelta(minutes=1)),
        "yanlis_issuer": _token(iss="https://baska-proje.supabase.co/auth/v1"),
        "yanlis_audience": _token(aud="anon"),
        "alg_none": _token("", algorithm="none"),
        "imzasiz_iki_parca": f"{header}.{payload}",
        "imza_bolumu_bos": f"{header}.{payload}.",
        "hs512": _token(algorithm="HS512"),
        "gecersiz_base64_govde": _signed_garbage_payload_token(),
    }


class TestBozukTokenReddi:
    """Dokuz vakanın token taşıyanları. Her biri 401 + `unauthenticated` döner."""

    async def test_forged_signature_is_rejected(self, auth_client: AsyncClient) -> None:
        """Yapısı kusursuz ama BAŞKA bir anahtarla imzalanmış token.

        Supabase'de JWT secret'ı proje başına ayrıdır; bu vaka "başka bir projenin
        kullanıcısı bizim kullanıcımız olabilir mi" sorusunun karşılığıdır.
        """
        response = await auth_client.get(
            PROTECTED_PATH, headers=_bearer(_token(OTHER_PROJECT_TEST_SECRET))
        )

        error = _assert_unauthorized(response)
        assert error["message"] == MESSAGE_INVALID_SESSION

    async def test_expired_token_is_rejected(self, auth_client: AsyncClient) -> None:
        """`exp` geçmişte. Çalınmış bir token'ın ömrü budur; sonsuz olamaz."""
        expired = datetime.now(tz=UTC) - timedelta(minutes=1)

        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(_token(exp=expired)))

        error = _assert_unauthorized(response)
        assert error["message"] == MESSAGE_INVALID_SESSION

    async def test_wrong_issuer_is_rejected(self, auth_client: AsyncClient) -> None:
        """`iss` sabitlenmişken başka bir projenin issuer'ı kabul edilmez."""
        response = await auth_client.get(
            PROTECTED_PATH,
            headers=_bearer(_token(iss="https://baska-proje.supabase.co/auth/v1")),
        )

        _assert_unauthorized(response)

    async def test_wrong_audience_is_rejected(self, auth_client: AsyncClient) -> None:
        """`aud: anon` Supabase'in anonim anahtarına aittir; oturum sahibi değildir."""
        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(_token(aud="anon")))

        _assert_unauthorized(response)

    async def test_unsigned_alg_none_token_is_rejected(self, auth_client: AsyncClient) -> None:
        """Klasik JWT açığı: imzasız token 'doğrulanmış' sayılırsa herkes herkes olur.

        Token'ın gerçekten `{"alg": "none"}` başlığı taşıdığı ve imza bölümünün boş
        olduğu önce doğrulanıyor; aksi hâlde bu test, açık kapatılmadan da yeşil
        yanabilirdi.
        """
        unsigned = _token("", algorithm="none")
        assert jwt.get_unverified_header(unsigned)["alg"] == "none"
        assert unsigned.endswith(".")

        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(unsigned))

        _assert_unauthorized(response)

    @pytest.mark.parametrize("case", ["imzasiz_iki_parca", "imza_bolumu_bos"])
    async def test_token_without_signature_is_rejected(
        self, auth_client: AsyncClient, case: str
    ) -> None:
        """İmza bölümü çıkarılmış token — iki biçimde.

        `header.payload` iki parçalıdır ve çözümleyicide düşer; `header.payload.`
        üç parçalı görünür ama imzası boştur. İkisi kodda farklı dallardan geçer,
        bu yüzden ikisi de sınanıyor.
        """
        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(_rejected_tokens()[case]))

        _assert_unauthorized(response)

    async def test_hs512_signed_token_is_rejected(self, auth_client: AsyncClient) -> None:
        """Algoritma karışması: DOĞRU anahtar, izin verilmeyen algoritma.

        Anahtar kasten doğru olanıdır — reddin sebebi imza uyuşmazlığı değil,
        izin listesinin yalnız HS256 içermesidir. Yanlış anahtarla imzalansaydı
        test, algoritma kapısı tamamen kaldırılsa bile yeşil yanardı.
        """
        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(_token(algorithm="HS512")))

        _assert_unauthorized(response)

    async def test_invalid_base64_payload_is_rejected(self, auth_client: AsyncClient) -> None:
        """Gövdesi base64 olmayan token; imzası o gövdeye göre doğru tutturulmuş."""
        response = await auth_client.get(
            PROTECTED_PATH, headers=_bearer(_signed_garbage_payload_token())
        )

        _assert_unauthorized(response)


class TestBozukAuthorizationBasligi:
    """Sekizinci vaka: token'a hiç sıra gelmeden başlığın kendisi bozuk."""

    @pytest.mark.parametrize(
        "header_value",
        [
            pytest.param("", id="bos-baslik"),
            pytest.param("Bearer", id="token-yok"),
            pytest.param("Bearer ", id="token-bos"),
            pytest.param("Basic {token}", id="yanlis-sema"),
            pytest.param("{token}", id="sema-yok"),
            pytest.param("Bearer{token}", id="bosluk-yok"),
            pytest.param("Bearer, {token}", id="bozuk-ayrac"),
        ],
    )
    async def test_malformed_authorization_header_is_rejected(
        self, auth_client: AsyncClient, header_value: str
    ) -> None:
        """Şema adı ve token, tek bir boşlukla ayrılmalıdır.

        Bu vakaların hepsi GEÇERLİ bir token ile kuruluyor: reddedilen şey token
        değil, başlığın biçimi. Bozuk token kullanılsaydı test, başlık ayrıştırması
        tümüyle kaldırılsa bile yeşil yanardı.
        """
        response = await auth_client.get(
            PROTECTED_PATH, headers={"Authorization": header_value.format(token=_token())}
        )

        error = _assert_unauthorized(response)
        assert "Bearer" not in error["message"], "hata metni başlık biçimini öğretmemeli"


class TestBilgiSizintisi:
    """Ret sebebi istemciye söylenmez (Anayasa IV, `security.py` modül başlığı).

    "Token süresi doldu" ile "imza geçersiz" arasındaki farkı vermek, elindeki
    token'ın hangi bakımdan bozuk olduğunu saldırgana ÖLÇTÜRÜR: çalınmış bir
    token'ın hâlâ taze olup olmadığı bu farkla anlaşılır.
    """

    async def test_all_rejections_share_one_message_and_code(
        self, auth_client: AsyncClient
    ) -> None:
        codes: set[str] = set()
        messages: set[str] = set()
        for token in _rejected_tokens().values():
            response = await auth_client.get(PROTECTED_PATH, headers=_bearer(token))
            error = _assert_unauthorized(response)
            codes.add(error["code"])
            messages.add(error["message"])

        assert codes == {"unauthenticated"}
        assert messages == {MESSAGE_INVALID_SESSION}

    async def test_rejection_body_does_not_echo_the_token(self, auth_client: AsyncClient) -> None:
        """Token yanıt gövdesine yansımaz; aksi hâlde log ve hata ekranı onu taşır."""
        token = _token(OTHER_PROJECT_TEST_SECRET)

        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(token))

        _assert_unauthorized(response)
        assert token not in response.text


class TestPozitifKontrol:
    """Dokuz negatif testin bir şey ölçtüğünün kanıtı.

    Kimlik doğrulaması tümüyle kırık (her isteği reddeden) bir uygulamada
    yukarıdaki testlerin hepsi yeşil yanardı. Aşağıdaki iki test o ihtimali kapatır.
    """

    async def test_valid_token_reaches_the_endpoint(
        self, auth_client: AsyncClient, users: UserFactory
    ) -> None:
        user_id = await users.create("negatif-kontrol@dogus.edu.tr", "Ayşe Yılmaz")

        response = await auth_client.get(PROTECTED_PATH, headers=_bearer(_token(sub=str(user_id))))

        assert response.status_code == 200, response.text
        assert UUID(response.json()["id"]) == user_id

    async def test_lowercase_bearer_scheme_is_accepted(
        self, auth_client: AsyncClient, users: UserFactory
    ) -> None:
        """RFC 7235 şema adını büyük/küçük harf duyarsız tanımlar.

        Bozuk başlık testlerinin yanında durması gerekiyor: şema karşılaştırması
        yanlışlıkla tam eşleşmeye çevrilirse o testler yeşil kalır, kırılan tek
        şey küçük harfli şema gönderen gerçek istemciler olurdu.
        """
        user_id = await users.create("negatif-kontrol-2@dogus.edu.tr")

        response = await auth_client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"bearer {_token(sub=str(user_id))}"},
        )

        assert response.status_code == 200, response.text
