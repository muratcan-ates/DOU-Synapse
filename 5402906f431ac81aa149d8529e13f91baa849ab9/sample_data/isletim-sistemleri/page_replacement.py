"""Sayfa değiştirme algoritmalarının benzetimi — BİLİNÇLİ OLARAK HATALI (bug_hunt).

Bu dosya ders materyalinin bir parçasıdır. Üç algoritma uygulanmıştır: FIFO, LRU ve
Clock. İkisi doğrudur; **birinde kasıtlı bir hata vardır.** Hata istisna üretmez;
benzetim çalışır, makul görünen sayılar basar ve küçük örneklerde çoğu zaman doğru
sonucu bile verir.

Kavramsal anlatım `07-virtual-memory.pdf` §3 içindedir.

İpucu (cevap değil): bir algoritmanın FIFO'dan ayrılan tek davranışı, ISABET
durumunda ne yaptığıdır.
"""

from __future__ import annotations

from collections import deque


def fifo(referanslar: list[int], cerceve_sayisi: int) -> int:
    """İlk giren ilk çıkar. Dönen değer sayfa hatası sayısıdır.

    Bu uygulama DOĞRUDUR ve diğerleri için karşılaştırma zeminidir.
    """
    bellek: deque[int] = deque()
    icinde: set[int] = set()
    hata = 0

    for sayfa in referanslar:
        if sayfa in icinde:
            continue
        hata += 1
        if len(bellek) == cerceve_sayisi:
            cikan = bellek.popleft()
            icinde.discard(cikan)
        bellek.append(sayfa)
        icinde.add(sayfa)

    return hata


def lru(referanslar: list[int], cerceve_sayisi: int) -> int:
    """En uzun süredir kullanılmayanı çıkarır. Dönen değer sayfa hatası sayısıdır."""
    bellek: deque[int] = deque()
    icinde: set[int] = set()
    hata = 0

    for sayfa in referanslar:
        if sayfa in icinde:
            # Sayfa bellekte: bu bir isabettir, sayfa hatası sayılmaz.
            continue

        hata += 1
        if len(bellek) == cerceve_sayisi:
            cikan = bellek.popleft()
            icinde.discard(cikan)
        bellek.append(sayfa)
        icinde.add(sayfa)

    return hata


def clock(referanslar: list[int], cerceve_sayisi: int) -> int:
    """İkinci şans algoritması. Dönen değer sayfa hatası sayısıdır.

    Bu uygulama DOĞRUDUR: her çerçevenin bir referans biti vardır, isabet bu biti
    1 yapar ve kurban ararken işaretçi 1 gördüğü biti sıfırlayıp ilerler.
    """
    cerceveler: list[int | None] = [None] * cerceve_sayisi
    referans_biti = [0] * cerceve_sayisi
    isaretci = 0
    hata = 0

    for sayfa in referanslar:
        if sayfa in cerceveler:
            referans_biti[cerceveler.index(sayfa)] = 1
            continue

        hata += 1
        while True:
            if cerceveler[isaretci] is None or referans_biti[isaretci] == 0:
                cerceveler[isaretci] = sayfa
                referans_biti[isaretci] = 1
                isaretci = (isaretci + 1) % cerceve_sayisi
                break
            referans_biti[isaretci] = 0
            isaretci = (isaretci + 1) % cerceve_sayisi

    return hata


def optimal(referanslar: list[int], cerceve_sayisi: int) -> int:
    """Gelecekte en uzun süre kullanılmayacak sayfayı çıkarır (OPT).

    Uygulanabilir bir algoritma değildir; diğerlerinin ne kadar iyi olduğunu
    ölçmek için bir alt sınır sağlar.
    """
    bellek: list[int] = []
    hata = 0

    for konum, sayfa in enumerate(referanslar):
        if sayfa in bellek:
            continue
        hata += 1
        if len(bellek) < cerceve_sayisi:
            bellek.append(sayfa)
            continue

        en_uzak = -1
        kurban = bellek[0]
        for aday in bellek:
            try:
                sonraki = referanslar.index(aday, konum + 1)
            except ValueError:
                kurban = aday
                break
            if sonraki > en_uzak:
                en_uzak = sonraki
                kurban = aday
        bellek[bellek.index(kurban)] = sayfa

    return hata


def belady_ornegi() -> None:
    """FIFO'nun Belady anomalisini gösterir: çerçeve artarken hata da artar."""
    referanslar = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    for cerceve in (3, 4):
        print(f"  FIFO  cerceve={cerceve}  hata={fifo(referanslar, cerceve)}")


if __name__ == "__main__":
    referanslar = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    cerceve = 3
    print(f"referans uzunlugu={len(referanslar)} cerceve={cerceve}")
    print(f"  FIFO    : {fifo(referanslar, cerceve)}")
    print(f"  LRU     : {lru(referanslar, cerceve)}")
    print(f"  Clock   : {clock(referanslar, cerceve)}")
    print(f"  Optimal : {optimal(referanslar, cerceve)}")
    print("Belady anomalisi:")
    belady_ornegi()
