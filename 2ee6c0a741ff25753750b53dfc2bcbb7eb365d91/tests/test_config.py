"""Ayarların ortam değişkeni adlarını sabitleyen testler.

Buradaki asıl test `test_env_example_adlarinin_hepsi_bir_ayara_baglanir`. Sebebi
9 Ağustos'ta bulunan bir kusur: `.env.example` `SUPABASE_JWT_ISSUER` diyordu,
`Settings` alanının adı ise `jwt_issuer`'dı ve pydantic-settings o alan için
`JWT_ISSUER` arıyordu. `model_config`'te `extra="ignore"` olduğu için tanınmayan
ad SESSİZCE atılıyordu: kurulum belgesini birebir uygulayan operatör hiçbir hata
almadan issuer doğrulamasını kapalı bırakıyordu — tam da `.env.example`'ın
"üretimde mutlaka doldurun" diye uyardığı ayarı.

Kusurun sınıfı tekil bir yazım hatası değil, **sessiz kabul**. Bu yüzden test tek
bir değişkeni değil, belgede adı geçen HER değişkeni tarar: yeni bir uyuşmazlık
eklendiğinde de kırmızı yanar (SC-015).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

#: `.env.example`'da geçen ama `Settings`'e ait OLMAYAN adlar. Her biri başka bir
#: tüketiciye ait; listede tutulmalarının sebebi "unutulmuş" ile "başkasının"
#: ayrımını açık tutmak.
NON_SETTINGS_NAMES = {
    # Docker imajı build argümanı (apps/api/Dockerfile), uygulama okumaz.
    "EMBEDDING_CACHE_DIR",
    # Değerlendirme betikleri okur (evaluation/), API süreci okumaz.
    "EVAL_LLM_API_KEY",
}


def _env_example_names() -> set[str]:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))


def _accepted_env_names() -> set[str]:
    """`Settings`'in gerçekten okuduğu ortam değişkeni adları.

    İki kaynak var: alan adının büyük harflisi (pydantic-settings varsayılanı) ve
    alanda açıkça tanımlanmış `validation_alias`. İkincisi olmadan alias'lı
    alanlar "tanınmıyor" görünürdü.
    """
    names: set[str] = set()
    for field_name, field in Settings.model_fields.items():
        names.add(field_name.upper())
        alias = field.validation_alias
        if alias is None:
            continue
        choices = getattr(alias, "choices", None)
        if choices is None:
            names.add(str(alias).upper())
        else:
            names.update(str(choice).upper() for choice in choices)
    return names


def test_env_example_adlarinin_hepsi_bir_ayara_baglanir() -> None:
    """Belgede adı geçen her değişken ya bir ayara bağlanır ya da listede olur.

    Bu testin kırmızı yanması "belge yanlış" demektir; yeşil yanması ise belgeyi
    birebir uygulayan operatörün ayarının gerçekten okunacağı anlamına gelir.
    """
    documented = _env_example_names()
    accepted = _accepted_env_names()
    orphans = documented - accepted - NON_SETTINGS_NAMES
    assert not orphans, (
        f".env.example şu adları belgeliyor ama Settings hiçbirini okumuyor: "
        f"{sorted(orphans)}. extra='ignore' bunları sessizce atar — operatör "
        f"hata almadan ayarı kapalı bırakır. Ya alana validation_alias ekleyin "
        f"ya da belgedeki adı düzeltin."
    )


@pytest.mark.parametrize("env_name", ["SUPABASE_JWT_ISSUER", "JWT_ISSUER"])
def test_issuer_iki_adla_da_okunur(env_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Belgedeki ad ve alan adından türeyen ad, ikisi de çalışmalı.

    `SUPABASE_JWT_ISSUER` belgenin söylediği ad; `JWT_ISSUER` alias eklenmeden
    önce fiilen çalışan tek ad. İkincisi geriye uyumluluk için korunuyor —
    alias'ı tek ada indirmek, alanı bugün doğru kurmuş bir ortamı bozardı.
    """
    monkeypatch.setenv(env_name, "https://ornek.supabase.co/auth/v1")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.jwt_issuer == "https://ornek.supabase.co/auth/v1"


def test_issuer_verilmezse_none_kalir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Varsayılan davranış değişmedi: ayar yoksa issuer doğrulanmaz.

    Bu davranış bilinçli (`security.py` issuer yoksa kontrolü atlar) ve alias
    eklenmesi onu değiştirmemeli — değiştirseydi anahtarsız yerel geliştirme
    kırılırdı.
    """
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.jwt_issuer is None
