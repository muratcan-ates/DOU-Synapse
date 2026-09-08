"""Süreç içi eşzamanlılık kapısı.

İstek sayısı kotası `request_quota.py` üzerinden PostgreSQL'de paylaşılır.
Bu modülün kapısı yalnız aynı süreçteki aktif işleri sayar; qgen için sunucular
arası eşzamanlılık garantisi sağlamaz. Sohbet ayrıca kalıcı token/iş rezervasyonu
kullanır. Burada istek sayısı için yerel sayaç veya sessiz fallback bulunmaz.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.errors import ConcurrencyLimitError


def _compose(scope: str, key: str) -> str:
    return f"{scope}:{key}"


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
_gate = ConcurrencyGate()


def get_concurrency_gate() -> ConcurrencyGate:
    return _gate


def reset_rate_limit() -> None:
    """Testler için süreç içi eşzamanlılık kapısını sıfırlama.

    Adı `chat.py`'deki hâliyle korundu: üç test dosyası bu adı `app.api.chat`
    üzerinden ithal ediyor ve taşıma sırasında sessizce kırılmamalı. Artık
    yalnız süreç içi kapıyı sıfırlar. Kalıcı kota durumunu veya üretim
    veritabanını değiştirmez; test DB fixture temizliği ayrıdır.
    """
    _gate.reset()


__all__ = [
    "ConcurrencyGate",
    "get_concurrency_gate",
    "reset_rate_limit",
]
