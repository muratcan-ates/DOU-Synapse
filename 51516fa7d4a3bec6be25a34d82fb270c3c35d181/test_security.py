"""`app/core/security.py` — JWT doğrulamasının davranış testleri.

Hepsi veritabanısızdır: buradaki tek soru "bu token'ın sahibi kim ve token geçerli mi".
Yetkilendirme (kim hangi derse erişir) `api/deps.py` ve RLS'in işidir.

Sınanan yedi vaka 11_R1_KIMLIK.md'de sayılıdır; üzerine `iss`/`aud` claim'lerinin
VARLIĞI, algoritma izin listesi ve hata mesajının ayrım yapmaması eklendi.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.core.security import MESSAGE_INVALID_SESSION, Principal, authenticate

# Gerçek Supabase JWT secret'ları uzundur; HS256 için 32 bayttan kısa anahtar PyJWT'de
# uyarı üretir. Test anahtarları da bu eşiğin üstünde tutuluyor.
SECRET = "dou-synapse-test-jwt-secret-32-bayttan-uzun"
OTHER_SECRET = "baska-bir-supabase-projesinin-secreti-uzun"
ISSUER = "https://proje.supabase.co/auth/v1"


class SettingsWithIssuer(Settings):
    """`jwt_issuer` alanı eklenmiş ayarlar.

    Alan `config.py`'de HENÜZ YOK (lider dosyası; bkz. security.py::_expected_issuer).
    Kod alanı `getattr` ile okuduğu için buradaki alt sınıf, alan eklendiğinde ne
    olacağını bugünden ölçer: rapor "eklenince çalışacak" demiyor, çalıştığını
    gösteriyor (Anayasa III).
    """

    jwt_issuer: str | None = None


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "local",
        "supabase_jwt_secret": SECRET,
        "dev_auth_enabled": False,
    }
    values.update(overrides)
    if "jwt_issuer" in values:
        return SettingsWithIssuer(**values)
    return Settings(**values)


def _token(secret: str = SECRET, *, algorithm: str = "HS256", **overrides: Any) -> str:
    """Supabase'in ürettiğine biçimsel olarak denk bir token üretir.

    `None` verilen claim tamamen ÇIKARILIR — "eksik claim" vakaları böyle kurulur.
    """
    now = datetime.now(tz=UTC)
    claims: dict[str, Any] = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "email": "ayse@dogus.edu.tr",
    }
    claims.update(overrides)
    return jwt.encode(
        {k: v for k, v in claims.items() if v is not None}, secret, algorithm=algorithm
    )


class TestGecerliToken:
    def test_gecerli_token_principal_dondurur(self) -> None:
        user_id = uuid4()

        principal = authenticate(_token(sub=str(user_id)), _settings())

        assert principal == Principal(user_id=user_id, email="ayse@dogus.edu.tr")

    def test_eposta_yoksa_none_olur(self) -> None:
        principal = authenticate(_token(email=None), _settings())

        assert principal.email is None

    def test_bosluklu_token_kirpilir(self) -> None:
        user_id = uuid4()

        principal = authenticate(f"  {_token(sub=str(user_id))}  ", _settings())

        assert principal.user_id == user_id


class TestReddedilenTokenlar:
    def test_suresi_gecmis_token_reddedilir(self) -> None:
        expired = datetime.now(tz=UTC) - timedelta(minutes=1)

        with pytest.raises(AuthenticationError):
            authenticate(_token(exp=expired), _settings())

    def test_yanlis_anahtarla_imzalanmis_token_reddedilir(self) -> None:
        """Başka bir Supabase projesinin token'ı: imza anahtarı proje başına ayrıdır."""
        with pytest.raises(AuthenticationError):
            authenticate(_token(OTHER_SECRET), _settings())

    def test_aud_yanlissa_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(aud="anon"), _settings())

    def test_sub_uuid_degilse_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(sub="ayse"), _settings())

    def test_sub_metin_degilse_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(sub=12345), _settings())

    def test_algoritma_none_reddedilir(self) -> None:
        """Klasik JWT açığı: imzasız token 'doğrulanmış' sayılırsa herkes herkes olur.

        Token gerçekten `{"alg":"none"}` başlığıyla ve imzasız üretiliyor; testin
        kendisi de bunu doğruluyor, aksi hâlde açık kapatılmadan yeşil yanabilirdi.
        """
        unsigned = _token("", algorithm="none")
        assert jwt.get_unverified_header(unsigned)["alg"] == "none"
        assert unsigned.endswith(".")

        with pytest.raises(AuthenticationError):
            authenticate(unsigned, _settings())

    def test_izin_listesi_none_iceriyorsa_bile_reddedilir(self) -> None:
        """Ayar dosyasına yanlışlıkla `none` yazılması senaryosu.

        `config.py` bu şeridin sahipliğinde değil; savunma bu yüzden tüketim
        noktasında duruyor ve testi burada.
        """
        unsigned = _token("", algorithm="none")

        with pytest.raises(AuthenticationError):
            authenticate(unsigned, _settings(jwt_algorithms=["none"]))

    def test_bos_token_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate("   ", _settings())

    def test_bicimsiz_token_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate("bu-bir-jwt-degil", _settings())


class TestZorunluClaimler:
    """PyJWT eksik claim'i sessizce görmezden gelir; `require` olmadan bu üç vaka geçerdi."""

    def test_exp_yoksa_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(exp=None), _settings())

    def test_aud_yoksa_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(aud=None), _settings())

    def test_iss_yoksa_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(iss=None), _settings())

    def test_sub_yoksa_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(_token(sub=None), _settings())


class TestIssuerSabitleme:
    """`jwt_issuer` ayarı eklendiğinde davranış — bugün alan yok, kod hazır."""

    def test_issuer_ayarlanmissa_yanlis_issuer_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate(
                _token(iss="https://baska-proje.supabase.co/auth/v1"),
                _settings(jwt_issuer=ISSUER),
            )

    def test_issuer_ayarlanmissa_dogru_issuer_kabul_edilir(self) -> None:
        principal = authenticate(_token(), _settings(jwt_issuer=ISSUER))

        assert isinstance(principal.user_id, UUID)

    def test_issuer_ayarli_degilken_iss_degeri_sabitlenmez(self) -> None:
        """Bugünkü davranışın dürüst kaydı: `iss` isteniyor ama sabitlenmiyor.

        Bu testin yeşil olması bir güvence değil, bir SINIRIN kaydıdır. Alan eklendiği
        gün bu test kırmızıya döner ve o an `docs/security.md`'deki "uygulanmadı"
        satırı da silinir.
        """
        principal = authenticate(_token(iss="https://baska-proje.supabase.co/auth/v1"), _settings())

        assert isinstance(principal.user_id, UUID)


class TestGelistirmeKimligi:
    def test_dev_kimligi_uretimde_reddedilir(self) -> None:
        """Bu şeridin en kritik testi.

        `DEV_AUTH_ENABLED` kapalıyken `Bearer dev:<uuid>` kabul edilseydi, token'ı
        imzalamaya bile gerek kalmadan herkes istediği kullanıcı olurdu. `config.py`
        bayrağı üretim ortamında zaten açtırmıyor; bu ikinci kapının testi.
        """
        with pytest.raises(AuthenticationError):
            authenticate(f"dev:{uuid4()}", _settings(dev_auth_enabled=False))

    def test_dev_kimligi_acikken_kabul_edilir(self) -> None:
        user_id = uuid4()

        principal = authenticate(f"dev:{user_id}", _settings(dev_auth_enabled=True))

        assert principal == Principal(user_id=user_id, email=None)

    def test_dev_kimligi_uuid_degilse_reddedilir(self) -> None:
        with pytest.raises(AuthenticationError):
            authenticate("dev:ayse", _settings(dev_auth_enabled=True))

    def test_dev_oneki_buyuk_harfle_yazilirsa_imza_yolu_isler(self) -> None:
        """`DEV:` bir kaçış yolu değildir: ön eki tutmayan token imzalı yola düşer."""
        with pytest.raises(AuthenticationError):
            authenticate(f"DEV:{uuid4()}", _settings(dev_auth_enabled=True))


class TestBilgiSizintisi:
    def test_butun_ret_sebepleri_ayni_mesaji_dondurur(self) -> None:
        """Mesaj farkı, saldırgana token'ının hangi bakımdan bozuk olduğunu ölçtürür.

        Süresi dolmuş bir token ile yanlış anahtarla imzalanmış bir token arasındaki
        ayrım, çalınmış bir token'ın hâlâ "taze" olup olmadığını söyler.
        """
        settings = _settings()
        bozuk_tokenlar = [
            _token(exp=datetime.now(tz=UTC) - timedelta(minutes=1)),
            _token(OTHER_SECRET),
            _token(aud="anon"),
            _token(iss=None),
            _token(sub="ayse"),
            _token("", algorithm="none"),
            f"dev:{uuid4()}",
            "bu-bir-jwt-degil",
        ]

        mesajlar = set()
        for token in bozuk_tokenlar:
            with pytest.raises(AuthenticationError) as hata:
                authenticate(token, settings)
            mesajlar.add(hata.value.message)

        assert mesajlar == {MESSAGE_INVALID_SESSION}

    def test_ret_sebebi_loga_yazilir_token_yazilmaz(self, caplog: pytest.LogCaptureFixture) -> None:
        """Ayrım kullanıcıdan gizlenir ama kaybolmaz: operatör logdan görür."""
        token = _token(OTHER_SECRET)

        with (
            caplog.at_level(logging.WARNING, logger="app.auth"),
            pytest.raises(AuthenticationError),
        ):
            authenticate(token, _settings())

        kayit = "\n".join(caplog.messages)
        assert "kimlik doğrulama reddi" in kayit
        assert token not in kayit
