"""Yetki yüzeyi denetimi: her rota bir kimlik bağımlılığı taşımalı (F1 tamamlayıcısı).

## Neden bu dosya var

`test_auth_negative.py` bozuk bir JWT'nin 401 aldığını kanıtlar. O test, kimlik
kontrolünün OLDUĞU uçlarda kontrolün doğru çalıştığını gösterir; kimlik kontrolü
HİÇ OLMAYAN bir uç için hiçbir şey söylemez. Korumasız bir rota eklemek için
kötü niyet gerekmez: yeni bir `@router.get` yazılırken `PrincipalDep` unutulur,
tüm testler yeşil kalır ve uç herkese açık gider. Depoda bugün 80'in üzerinde
rota var; bunu göz kontrolüne bırakmak, ölçmeden "güvenli" demektir.

Bu test uygulamanın TÜM rotalarını gezer ve her birinin bağımlılık ağacında
`app/api/deps.py` içindeki kimlik kapılarından en az birini arar. Bilerek açık
olan uçlar aşağıdaki beyaz listede, her biri tek cümlelik gerekçesiyle durur.
Yeni bir rota kimlik bağımlılığı olmadan eklenirse bu test KIRMIZI yanar; onu
yeşile çevirmenin tek yolu ya bağımlılığı eklemek ya da gerekçesiyle beyaz
listeye yazmaktır — ikisi de incelemede görünür.

## Sınır

Bağımlılığın VARLIĞI ölçülür, doğru davranışı değil; davranış `test_auth_negative`
ve rol testlerinde. `/internal/*` uçları kimlik yerine paylaşılan sırla korunur
(`get_settings` üzerinden, `internal.py`); bu test sırrın varlığını değil, uçların
bilerek listede olduğunu kaydeder.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

#: Kimlik kapısı sayılan bağımlılıklar. `get_session` de listede: `SessionDep`
#: `get_principal`'ı zorunlu kılar (deps.py), yani oturum alan her uç kimlikli.
#: Adlar `_identity_gates` içinde gerçek fonksiyonlarla doğrulanır; burada
#: metin olarak durmaları, bir kapı yeniden adlandırılırsa testin gürültüyle
#: (KeyError ile değil, iddia ile) düşmesi içindir.
IDENTITY_GATE_NAMES: tuple[str, ...] = (
    "get_principal",
    "get_session",
    "require_course_member",
    "require_course_instructor",
    "require_platform_admin",
    "require_assistant_unlocked",
)


def _identity_gates() -> frozenset[str]:
    # `app.main` modül düzeyinde `create_app()` çağırır ve bu, Settings'i okur;
    # conftest'in ortam fixture'ı testler koşmadan önce hazır olduğu için içe
    # aktarma toplama anında değil, test gövdesinde yapılır.
    from app.api import deps

    missing = [name for name in IDENTITY_GATE_NAMES if not hasattr(deps, name)]
    assert missing == [], f"deps.py'de artık olmayan kimlik kapısı: {missing}"
    return frozenset(IDENTITY_GATE_NAMES)


def _app() -> FastAPI:
    from app.main import create_app

    return create_app()


#: Bilerek kimliksiz uçlar. Anahtar `(yöntem, yol)`, değer tek cümlelik gerekçe.
#: Buraya eklenen her satır bir güvenlik kararıdır ve incelemede okunur.
INTENTIONALLY_PUBLIC: dict[tuple[str, str], str] = {
    ("GET", "/health/live"): "Canlılık probu; veri döndürmez, yük dengeleyici kimlik taşıyamaz.",
    ("GET", "/health/ready"): "Hazırlık probu; yalnız DB/pgvector durumu, dağıtım hattı okur.",
    ("GET", "/docs"): (
        "Swagger kabuğu; /openapi.json platform yöneticisi ister, kabuk tek başına şema sızdırmaz."
    ),
    ("POST", "/internal/drain"): (
        "Paylaşılan sırla korunur (internal.py); sırsız istek 403/404 — deploy dumanı bunu ölçer."
    ),
    ("GET", "/internal/evaluation/runtime"): (
        "Paylaşılan sırla korunur (internal.py); sır yoksa 404."
    ),
}


def _flatten(dependant: Dependant, acc: set[str]) -> set[str]:
    for child in dependant.dependencies:
        acc.add(getattr(child.call, "__name__", repr(child.call)))
        _flatten(child, acc)
    return acc


def _walk(routes: list[object]) -> Iterator[APIRoute]:
    # FastAPI, include_router ile eklenen router'ları tembel bir sarmalayıcıda
    # tutuyor; gerçek rotalar `original_router` altında. Sarmalayıcı adı özel
    # olduğu için türe değil özniteliğe bakılır.
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        else:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                yield from _walk(list(inner.routes))


def _surface(app: FastAPI) -> dict[tuple[str, str], set[str]]:
    surface: dict[tuple[str, str], set[str]] = {}
    for route in _walk(list(app.routes)):
        names = _flatten(route.dependant, set())
        for method in sorted(route.methods or ()):
            surface[(method, route.path)] = names
    return surface


class TestAuthSurface:
    def test_every_route_has_an_identity_gate_or_a_written_reason(self) -> None:
        gates = _identity_gates()
        surface = _surface(_app())
        assert len(surface) > 50, "rota ağacı gezilemedi; sarmalayıcı değişmiş olabilir"

        unprotected = sorted(key for key, names in surface.items() if not names & gates)
        unexplained = [key for key in unprotected if key not in INTENTIONALLY_PUBLIC]
        assert unexplained == [], (
            "kimlik bağımlılığı olmayan ve beyaz listede gerekçesi yazılmamış uç(lar): "
            f"{unexplained} — ya PrincipalDep/SessionDep ekle ya da INTENTIONALLY_PUBLIC'e "
            "tek cümlelik gerekçeyle yaz"
        )

    def test_whitelist_carries_no_dead_entries(self) -> None:
        # Beyaz listede artık var olmayan ya da artık kimlikli bir uç durmamalı:
        # bayat istisna, ileride aynı yola eklenecek korumasız bir ucu maskeler.
        gates = _identity_gates()
        surface = _surface(_app())
        for key, reason in INTENTIONALLY_PUBLIC.items():
            assert key in surface, f"beyaz listedeki uç yok: {key}"
            assert not (surface[key] & gates), f"artık kimlikli, listeden düş: {key}"
            assert reason.strip().endswith("."), f"gerekçe tam cümle olmalı: {key}"

    def test_internal_routes_are_settings_gated_not_identity_gated(self) -> None:
        # /internal/* kimlik yerine sır ister; sırrı okuyan bağımlılık ağaçta görünmeli.
        surface = _surface(_app())
        internal = {key: names for key, names in surface.items() if key[1].startswith("/internal/")}
        assert internal, "/internal rotaları bulunamadı"
        for key, names in internal.items():
            assert "get_settings" in names, f"{key} sır ayarını okumuyor"
