"""Süreç içi kabul kontrolü: hız sınırı (FR-222) ve eşzamanlılık kapısı (FR-223).

Sınıf `api/chat.py`'nin içinde yaşıyordu. İkinci bir uç (soru üretimi) aynı
davranışa ihtiyaç duyunca üç seçenek vardı: kopyalamak (Anayasa XI'in adıyla
yasakladığı şey), `questions.py`'nin `chat.py`'den özel bir adı ithal etmesi (iki
ucu birbirine kilitler) ya da ortak bir yere taşımak. Üçüncüsü seçildi ve yer
`core/` çünkü hız sınırı bir alan kuralı değil, `config`/`errors`/`logging` gibi
kesişen altyapıdır; `modules/` altındaki her klasör bir ürün yeteneğine ait.

## Kapsam adı neden ZORUNLU

Tek örnek iki uç tarafından paylaşılıyor ve ikisinin de doğal anahtarı
`kullanıcı:ders`. Kapsam olmasaydı iki uç aynı sayacı tüketirdi: bir öğretmen
sohbet ettiği için soru üretemez hâle gelirdi ve bu, kimsenin aramayacağı bir
kusur olurdu. Kapsamı imzada zorunlu kılmak hatayı çağrı yazılırken yakalar.

## Dürüst sınırlar (Anayasa III)

* Sayaç **süreç içidir.** Birden fazla uvicorn worker'ı koştuğunda sınır worker
  başına uygulanır; MVP tek süreçle koşuyor. Dağıtık sınır Redis ister ve
  kapsam dışı bırakıldı.
* Tahliye sızıntıyı **sınırlar, tamamen kapatmaz.** Süpürme eşiği görülen en
  büyük pencereye göre koşuyor; iki uç iki farklı pencere kullandığı için (60 sn
  ve 300 sn) kısa pencereli sohbet anahtarları 300 sn'ye kadar bellekte kalır.
  Sınırlı ve öngörülebilir bir üst sınır, ama sıfır değil.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.errors import ConcurrencyLimitError


def _compose(scope: str, key: str) -> str:
    return f"{scope}:{key}"


class SlidingWindowLimiter:
    """Kapsam + anahtar başına kayan pencere sayacı.

    Sınır ve pencere kurucuda değil `allow()` çağrısında verilir: değerler
    ayarlardan geliyor ve ayarlar isteğe bağlı bir bağımlılık. Sayaç süreç
    ömürlü, eşik ise istek başına okunuyor — böylece sayı değişince süreç
    yeniden başlatılmadan da geçerli olur.
    """

    def __init__(self) -> None:
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        #: Görülen en büyük pencere. Süpürme eşiği bundan türer; sabit yazılsaydı
        #: yeni bir uç daha uzun bir pencereyle geldiğinde sayaçları erken silerdi.
        self._max_window = 0.0
        self._last_sweep = time.monotonic()

    def allow(self, scope: str, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        self._max_window = max(self._max_window, window_seconds)
        self._sweep(now)

        hits = self._hits[_compose(scope, key)]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def retry_after(self, scope: str, key: str, *, window_seconds: float) -> float:
        """Kaç saniye sonra yeniden denenebileceği.

        Yer açacak olan şey en ESKİ vuruşun pencereden düşmesidir; sayı ondan
        hesaplanır. FR-222 reddin "ne zaman tekrar denenebilir" bilgisini
        taşımasını istiyor ve bu bilgi tahmin edilemez, hesaplanır.
        """
        hits = self._hits.get(_compose(scope, key))
        if not hits:
            return 0.0
        return max(0.0, window_seconds - (time.monotonic() - hits[0]))

    def _sweep(self, now: float) -> None:
        """Kullanılmayan anahtarları tahliye eder (FR-223).

        Bu satırlar olmadan sayaç süreç ömrü boyunca büyüyordu: her (kullanıcı,
        ders) çifti için bir deque açılıyor, boşalsa bile anahtarı hiç
        silinmiyordu; `reset()` yalnız testlerden çağrılıyor, üretimde hiç.

        Süpürme pencere başına en çok bir kez koşar. Her çağrıda taramak O(n)
        bir maliyeti sıcak yola koyardı; tahliyenin gerekçesi bellek, ve bellek
        milisaniye çözünürlüğünde bir sorun değil.
        """
        if now - self._last_sweep <= self._max_window:
            return
        self._last_sweep = now
        stale = [
            key for key, hits in self._hits.items() if not hits or now - hits[-1] > self._max_window
        ]
        for key in stale:
            del self._hits[key]

    def tracked_keys(self) -> int:
        """Şu an bellekte tutulan anahtar sayısı. Tahliye testinin ölçtüğü sayı."""
        return len(self._hits)

    def reset(self) -> None:
        self._hits.clear()
        self._max_window = 0.0
        self._last_sweep = time.monotonic()


class ConcurrencyGate:
    """Aynı anahtar için eşzamanlı iş sayısını sınırlar.

    Kontrol ile sayaç artırma arasında `await` YOKTUR; asyncio tek iş
    parçacıklı olduğu için bu ikisi bölünemez ve yarış oluşmaz. Bir
    `asyncio.Lock` eklemek yanlış bir güvence duygusu verirdi: koruduğu şey
    zaten bölünmüyor.

    Anahtar sayacı sıfıra düştüğünde SİLİNİR — sızıntı, sınırlayıcıdakinin
    aksine süpürme gerektirmiyor, çünkü her tutuş bir bırakışla kapanıyor.
    """

    def __init__(self) -> None:
        self._active: defaultdict[str, int] = defaultdict(int)

    @contextmanager
    def hold(self, scope: str, key: str, *, limit: int, message: str) -> Iterator[None]:
        """Yer varsa gövdeyi koşturur, yoksa `ConcurrencyLimitError` fırlatır.

        Bağlam yöneticisi bilinçli: `try/finally`'yi çağrı yerine bırakmak,
        gövde bir istisnayla çıktığında sayacın sonsuza kadar dolu kalması
        riskini her çağrı yerinde yeniden hatırlamayı gerektirirdi.

        Kullanıcıya dönecek cümle DIŞARIDAN geliyor: mekanizma burada, ama
        hangi işin sürdüğünü ve kullanıcının ne yapması gerektiğini yalnız uç
        bilir (Anayasa V — metin, bağlamı bilen yerde yazılır).
        """
        composed = _compose(scope, key)
        if self._active[composed] >= limit:
            # Sayaç artırılmadan çıkılıyor; `defaultdict` erişimi bir anahtar
            # yaratmış olabilir, aşağıda temizleniyor.
            if self._active[composed] == 0:
                del self._active[composed]
            raise ConcurrencyLimitError(message)

        self._active[composed] += 1
        try:
            yield
        finally:
            self._active[composed] -= 1
            if self._active[composed] <= 0:
                del self._active[composed]

    def active(self, scope: str, key: str) -> int:
        return self._active.get(_compose(scope, key), 0)

    def reset(self) -> None:
        self._active.clear()


#: Tek paylaşılan örnekler. İki uç da bunları kullanır; ikinci bir kopya
#: yazılmaz (Anayasa XI).
_limiter = SlidingWindowLimiter()
_gate = ConcurrencyGate()


def get_limiter() -> SlidingWindowLimiter:
    return _limiter


def get_concurrency_gate() -> ConcurrencyGate:
    return _gate


def reset_rate_limit() -> None:
    """Testler için sayaç sıfırlama.

    Adı `chat.py`'deki hâliyle korundu: üç test dosyası bu adı `app.api.chat`
    üzerinden ithal ediyor ve taşıma sırasında sessizce kırılmamalı. Artık
    eşzamanlılık kapısını da sıfırlıyor — yarım kalmış bir tutuş sonraki testi
    sebepsiz reddederdi.
    """
    _limiter.reset()
    _gate.reset()


__all__ = [
    "ConcurrencyGate",
    "SlidingWindowLimiter",
    "get_concurrency_gate",
    "get_limiter",
    "reset_rate_limit",
]
