"""Üretici-Tüketici (Producer-Consumer) örneği — sınırlı tampon (bounded buffer).

DİKKAT — BU DOSYA KASITLI OLARAK HATALIDIR (bug_hunt soru tipi için, T002).
Doğru sürüm 04-synchronization.md dosyasındadır. Buradaki hata: wait(empty)/wait(full)
çağrıları mutex'İ ALDIKTAN SONRA yapılıyor (doğrusu: mutex'ten ÖNCE ve dışında).

Bu sıralama hatasının sonucu: tampon doluyken üretici, mutex'i tutarken wait(empty)'de
sonsuza kadar bloke olabilir. Mutex tutulduğu sürece tüketici de mutex.acquire() içinde
bekler ve tamponu asla boşaltamaz -> KİLİTLENME (deadlock). Bu, doğrulanmış tek sonuçtur
(15/15 koşumda deadlock, PR incelemesinde ayrıca 30/30 koşumda deadlock; hiçbir koşumda
tampon taşması/taşınması gözlenmedi). Taşma/taşınma bu koddaki hatadan kaynaklanmaz;
o, `signal(full)`'ün ekleme işleminden önce çağrılması gibi AYRI bir hatanın sonucudur.
"""

from __future__ import annotations

import threading
from collections import deque

BUFFER_CAPACITY = 5


class BoundedBuffer:
    def __init__(self, capacity: int) -> None:
        self._queue: deque[int] = deque()
        self._capacity = capacity
        self._mutex = threading.Lock()
        # Sayan semaforlar: empty = boş yuva sayısı, full = dolu yuva sayısı.
        self._empty = threading.Semaphore(capacity)
        self._full = threading.Semaphore(0)

    def produce(self, item: int) -> None:
        # HATA: mutex önce alınıyor, wait(empty) mutex İÇİNDE çağrılıyor.
        # Doğrusu: self._empty.acquire() burada, mutex bloğundan ÖNCE ve dışında olmalı.
        with self._mutex:
            self._empty.acquire()  # <-- BUG: yanlış sıra, deadlock riski
            self._queue.append(item)
            self._full.release()

    def consume(self) -> int:
        # Aynı hata burada da tekrarlanıyor: wait(full) mutex içinde.
        with self._mutex:
            self._full.acquire()  # <-- BUG: yanlış sıra, deadlock riski
            item = self._queue.popleft()
            self._empty.release()
            return item


def run_demo() -> None:
    buffer = BoundedBuffer(BUFFER_CAPACITY)

    def producer() -> None:
        for i in range(10):
            buffer.produce(i)

    def consumer() -> None:
        for _ in range(10):
            buffer.consume()

    threads = [threading.Thread(target=producer), threading.Thread(target=consumer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    run_demo()
