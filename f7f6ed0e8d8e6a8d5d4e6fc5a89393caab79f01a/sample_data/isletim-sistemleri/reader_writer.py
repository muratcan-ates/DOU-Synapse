"""Okuyucu-Yazar problemi — BİLİNÇLİ OLARAK HATALI örnek (bug_hunt).

Bu dosya ders materyalinin bir parçasıdır ve içinde kasıtlı bir tasarım hatası vardır.
Hata bir çökme ya da istisna üretmez: program çalışır, tek okuyucuyla ve hafif yükte
kusursuz görünür. Sorun okuyucular üst üste bindiğinde ortaya çıkar.

Doğru davranışın anlatımı `04-synchronization.pdf` içindedir.

Aranan hata (cevap anahtarı öğretim elemanındadır, burada YAZILMAZ):
okuyucular arasında hiç boşluk kalmadığında `okuyucu_sayisi` sayacının sıfıra düşüp
düşmediğine, dolayısıyla yazarın beklediği kilidin ne zaman bırakıldığına bakınız.
"""

from __future__ import annotations

import threading
import time

# Aynı anda okuyan okuyucu sayısı. Yalnız `okuyucu_sayaci_kilidi` altında değiştirilir.
okuyucu_sayisi = 0
okuyucu_sayaci_kilidi = threading.Lock()

# Kaynağa erişimi düzenleyen kilit. İlk okuyucu alır, son okuyucu bırakır.
kaynak_kilidi = threading.Lock()

paylasilan_veri = {"deger": 0}

# Okuma ve yazma kritik bölgelerinin süresi. Gerçek bir iş yerine uyku kullanılıyor:
# ölçülmek istenen şey işin kendisi değil, kilidin ne kadar tutulduğu.
OKUMA_SURESI = 0.002
YAZMA_SURESI = 0.002


def okuyucu(bitis_zamani: float, sayaclar: dict[str, int]) -> None:
    """Süre dolana kadar durmadan okur.

    Okumalar arasında bilinçli olarak boşluk BIRAKILMAZ. Gerçek bir sistemde de
    okuma yükü yoğunlaştığında olan budur ve hatanın görünür hale geldiği koşul
    tam olarak budur.
    """
    global okuyucu_sayisi
    while time.perf_counter() < bitis_zamani:
        with okuyucu_sayaci_kilidi:
            okuyucu_sayisi += 1
            if okuyucu_sayisi == 1:
                # İlk okuyucu kaynağı yazarlara kapatır.
                kaynak_kilidi.acquire()

        # --- kritik bölge: okuma ---
        _ = paylasilan_veri["deger"]
        time.sleep(OKUMA_SURESI)
        # --- kritik bölge sonu ---

        with okuyucu_sayaci_kilidi:
            okuyucu_sayisi -= 1
            if okuyucu_sayisi == 0:
                # Son okuyucu kaynağı serbest bırakır.
                kaynak_kilidi.release()
            sayaclar["okuma"] += 1


def yazar(bitis_zamani: float, sayaclar: dict[str, int], bekleme: list[float]) -> None:
    """Süre dolana kadar yazmayı dener ve her denemede ne kadar beklediğini kaydeder."""
    while time.perf_counter() < bitis_zamani:
        istek_ani = time.perf_counter()
        # Süre dolduğunda asılı kalmamak için zaman aşımlı alınıyor. Zaman aşımı
        # hatanın parçası değil, ölçüm düzeneğinin parçası.
        alindi = kaynak_kilidi.acquire(timeout=max(0.0, bitis_zamani - istek_ani))
        if not alindi:
            bekleme.append(time.perf_counter() - istek_ani)
            return

        bekleme.append(time.perf_counter() - istek_ani)

        # --- kritik bölge: yazma ---
        paylasilan_veri["deger"] += 1
        time.sleep(YAZMA_SURESI)
        # --- kritik bölge sonu ---

        kaynak_kilidi.release()
        sayaclar["yazma"] += 1


def calistir(okuyucu_adedi: int, sure: float = 2.0) -> dict[str, float]:
    """Bir okuyucu yüküyle tek bir yazarı yarıştırır ve sonucu ölçer.

    Dönen sözlük: kaç okuma, kaç yazma yapıldı ve yazarın en uzun bekleyişi.
    """
    global okuyucu_sayisi
    okuyucu_sayisi = 0
    paylasilan_veri["deger"] = 0
    sayaclar = {"okuma": 0, "yazma": 0}
    bekleme: list[float] = []

    bitis = time.perf_counter() + sure
    threadler = [
        threading.Thread(target=okuyucu, args=(bitis, sayaclar)) for _ in range(okuyucu_adedi)
    ]
    threadler.append(threading.Thread(target=yazar, args=(bitis, sayaclar, bekleme)))

    for thread in threadler:
        thread.start()
    for thread in threadler:
        thread.join()

    # Okuyucular kilidi bırakmadan bitmiş olabilir; sonraki koşu için temizle.
    if kaynak_kilidi.locked():
        kaynak_kilidi.release()

    return {
        "okuyucu": okuyucu_adedi,
        "okuma": sayaclar["okuma"],
        "yazma": sayaclar["yazma"],
        "en_uzun_bekleme": max(bekleme) if bekleme else 0.0,
    }


if __name__ == "__main__":
    print(f"{'okuyucu':>8} {'okuma':>8} {'yazma':>8} {'en uzun bekleme (sn)':>22}")
    for adet in (1, 2, 4, 8):
        sonuc = calistir(adet)
        print(
            f"{sonuc['okuyucu']:>8.0f} {sonuc['okuma']:>8.0f} "
            f"{sonuc['yazma']:>8.0f} {sonuc['en_uzun_bekleme']:>22.3f}"
        )
