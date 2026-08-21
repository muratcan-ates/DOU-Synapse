"""Sınırlı tamponlu bir thread havuzu — DOĞRU örnek (code_trace).

Üretici-tüketici deseninin uygulamalı hâlidir: iş kuyruğu tampon, havuzdaki
thread'ler tüketicidir. `04-synchronization.pdf` içindeki semafor anlatımının
karşılığı burada `threading.Condition` ile kurulmuştur.

İzlenmesi istenen üç nokta:
  1. Kapanma isteği thread'lere nasıl duyuruluyor ve neden `notify_all` gerekiyor.
  2. `while` döngüsüyle beklemenin `if` ile beklemeye göre farkı.
  3. Kuyruk sınırının üreticiyi de bloke etmesi (geri basınç / backpressure).
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable

Is = Callable[[], None]


class ThreadHavuzu:
    """Sabit sayıda çalışan thread, sınırlı uzunlukta bir iş kuyruğu."""

    def __init__(self, calisan_sayisi: int = 4, kuyruk_siniri: int = 16) -> None:
        if calisan_sayisi < 1:
            raise ValueError("En az bir çalışan gerekir.")
        if kuyruk_siniri < 1:
            raise ValueError("Kuyruk sınırı en az 1 olmalı.")

        self._kuyruk: deque[Is] = deque()
        self._kuyruk_siniri = kuyruk_siniri
        self._kosul = threading.Condition()
        self._kapaniyor = False
        self._calisanlar = [
            threading.Thread(target=self._dongu, name=f"havuz-{index}", daemon=True)
            for index in range(calisan_sayisi)
        ]
        for calisan in self._calisanlar:
            calisan.start()

    def gonder(self, is_: Is) -> None:
        """Kuyruğa iş ekler. Kuyruk doluysa yer açılana kadar BLOKE OLUR.

        Bloke olmak bilinçlidir: kuyruğu sınırsız büyütmek, yavaş bir tüketicinin
        sorununu belleğe yazmak olurdu. Sınır, üreticiyi tüketicinin hızına
        bağlayan geri basıncı kurar.
        """
        with self._kosul:
            if self._kapaniyor:
                raise RuntimeError("Havuz kapanıyor, yeni iş kabul edilmiyor.")
            # `if` değil `while`: uyandırılmak koşulun sağlandığı anlamına gelmez.
            # Başka bir üretici araya girip yeri kapmış olabilir (sahte uyanma /
            # spurious wakeup ve yarış). Koşul her uyanışta yeniden sınanır.
            while len(self._kuyruk) >= self._kuyruk_siniri and not self._kapaniyor:
                self._kosul.wait()
            if self._kapaniyor:
                raise RuntimeError("Havuz kapanıyor, yeni iş kabul edilmiyor.")
            self._kuyruk.append(is_)
            # Tek bir iş eklendi; tek bir bekleyeni uyandırmak yeterli.
            self._kosul.notify()

    def _dongu(self) -> None:
        while True:
            with self._kosul:
                while not self._kuyruk and not self._kapaniyor:
                    self._kosul.wait()
                if self._kapaniyor and not self._kuyruk:
                    return
                is_ = self._kuyruk.popleft()
                # Kuyrukta yer açıldı; bekleyen bir üretici olabilir.
                self._kosul.notify()

            # İş kilit DIŞINDA çalıştırılır. Kilit tutularak çalıştırılsaydı havuz
            # tek thread'e inerdi ve varlık sebebi ortadan kalkardı.
            try:
                is_()
            except Exception as hata:  # noqa: BLE001
                # Tek bir işin hatası çalışanı öldürmemeli; öldürseydi havuz
                # zamanla boşalır ve sistem sessizce durur.
                print(f"iş başarısız: {hata!r}")

    def kapat(self, bekle: bool = True) -> None:
        """Yeni iş kabulünü durdurur, kuyruktakiler bittikten sonra çalışanlar döner."""
        with self._kosul:
            self._kapaniyor = True
            # `notify_all`: kapanmayı TÜM bekleyenlerin görmesi gerekir. `notify`
            # ile yalnız biri uyanır, diğerleri süresiz bekler ve `join` asılır.
            self._kosul.notify_all()
        if bekle:
            for calisan in self._calisanlar:
                calisan.join()


if __name__ == "__main__":
    kilit = threading.Lock()
    toplam = 0

    def artir(deger: int) -> Is:
        def calis() -> None:
            global toplam
            with kilit:
                toplam += deger

        return calis

    havuz = ThreadHavuzu(calisan_sayisi=4, kuyruk_siniri=8)
    for sayi in range(1, 101):
        havuz.gonder(artir(sayi))
    havuz.kapat()
    print(f"toplam={toplam} (beklenen 5050)")
