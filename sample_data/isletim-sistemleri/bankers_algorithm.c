/*
 * Banker's Algorithm — güvenlik (safety) denetimi ve kaynak isteği.
 *
 * DOĞRU örnek: kod inceleme sorularında (code_trace) izlenmek üzere yazıldı.
 * Kavramsal anlatımı 05-deadlock-demo.pdf içindedir.
 *
 * Derleme:  cc -std=c11 -Wall -Wextra -o banker bankers_algorithm.c
 */

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define SUREC_SAYISI 5
#define KAYNAK_TURU 3

/* Sistemdeki toplam kaynak sayısı, tür başına. */
static int toplam[KAYNAK_TURU] = {10, 5, 7};

/* Her sürecin en fazla isteyebileceği kaynak. */
static int azami[SUREC_SAYISI][KAYNAK_TURU] = {
    {7, 5, 3}, {3, 2, 2}, {9, 0, 2}, {2, 2, 2}, {4, 3, 3},
};

/* Her sürecin şu an elinde tuttuğu kaynak. */
static int tahsis[SUREC_SAYISI][KAYNAK_TURU] = {
    {0, 1, 0}, {2, 0, 0}, {3, 0, 2}, {2, 1, 1}, {0, 0, 2},
};

/*
 * Kullanılabilir kaynağı toplamdan tahsisleri düşerek hesaplar.
 * Ayrı tutulan bir "available" dizisi tahsislerle tutarsız kalabilirdi;
 * tek kaynaktan türetmek bu tutarsızlığı imkânsız kılar.
 */
static void kullanilabiliri_hesapla(int kullanilabilir[KAYNAK_TURU])
{
    for (int k = 0; k < KAYNAK_TURU; k++) {
        kullanilabilir[k] = toplam[k];
        for (int s = 0; s < SUREC_SAYISI; s++) {
            kullanilabilir[k] -= tahsis[s][k];
        }
    }
}

/* İhtiyaç = azami - tahsis. Sürecin daha ne kadar isteyebileceği. */
static void ihtiyaci_hesapla(int ihtiyac[SUREC_SAYISI][KAYNAK_TURU])
{
    for (int s = 0; s < SUREC_SAYISI; s++) {
        for (int k = 0; k < KAYNAK_TURU; k++) {
            ihtiyac[s][k] = azami[s][k] - tahsis[s][k];
        }
    }
}

/*
 * Güvenlik algoritması.
 *
 * Sistemin GÜVENLİ olması, tüm süreçlerin tamamlanmasını sağlayan en az bir
 * sıralamanın var olması demektir. Böyle bir sıralama bulunamazsa durum güvensizdir.
 *
 * Güvensiz olmak kilitlenmiş olmakla aynı şey DEĞİLDİR: güvensiz bir durumda
 * kilitlenme mümkün hale gelir, kaçınılmaz olmaz. Banker's algoritması sistemi
 * güvenli durumdan hiç çıkarmayarak kilitlenmeyi önler.
 *
 * `sira` NULL değilse bulunan güvenli sıralama oraya yazılır.
 */
static bool guvenli_mi(int sira[SUREC_SAYISI])
{
    int calisiyor[KAYNAK_TURU];
    int ihtiyac[SUREC_SAYISI][KAYNAK_TURU];
    bool bitti[SUREC_SAYISI] = {false};
    int bulunan = 0;

    kullanilabiliri_hesapla(calisiyor);
    ihtiyaci_hesapla(ihtiyac);

    /* Her turda tamamlanabilecek bir süreç ara; bulunamazsa döngü durur. */
    for (int tur = 0; tur < SUREC_SAYISI; tur++) {
        bool bu_turda_ilerledi = false;

        for (int s = 0; s < SUREC_SAYISI; s++) {
            if (bitti[s]) {
                continue;
            }
            bool karsilanabilir = true;
            for (int k = 0; k < KAYNAK_TURU; k++) {
                if (ihtiyac[s][k] > calisiyor[k]) {
                    karsilanabilir = false;
                    break;
                }
            }
            if (!karsilanabilir) {
                continue;
            }
            /* Süreç tamamlanabilir varsayılır ve tuttuğu her şeyi geri verir. */
            for (int k = 0; k < KAYNAK_TURU; k++) {
                calisiyor[k] += tahsis[s][k];
            }
            bitti[s] = true;
            if (sira != NULL) {
                sira[bulunan] = s;
            }
            bulunan++;
            bu_turda_ilerledi = true;
        }

        if (!bu_turda_ilerledi) {
            break;
        }
    }

    return bulunan == SUREC_SAYISI;
}

/*
 * Kaynak isteği.
 *
 * Üç denetim SIRAYLA yapılır ve sıra önemlidir:
 *   1. İstek, sürecin beyan ettiği azami ihtiyacı aşıyor mu?  -> hata
 *   2. İstek şu an karşılanabilir mi?                          -> beklet
 *   3. Karşılanırsa sistem güvenli kalır mı?                   -> karşılanmaz
 *
 * Üçüncü denetim algoritmanın özüdür: kaynak MEVCUT olsa bile, vermek sistemi
 * güvensiz duruma sokuyorsa verilmez. Bu yüzden Banker's bir kaçınma (avoidance)
 * algoritmasıdır, bir tespit algoritması değil.
 */
static bool istek_yap(int surec, const int istek[KAYNAK_TURU])
{
    int kullanilabilir[KAYNAK_TURU];
    int ihtiyac[SUREC_SAYISI][KAYNAK_TURU];

    kullanilabiliri_hesapla(kullanilabilir);
    ihtiyaci_hesapla(ihtiyac);

    for (int k = 0; k < KAYNAK_TURU; k++) {
        if (istek[k] > ihtiyac[surec][k]) {
            printf("P%d: istek beyan edilen azami ihtiyaci asiyor\n", surec);
            return false;
        }
    }
    for (int k = 0; k < KAYNAK_TURU; k++) {
        if (istek[k] > kullanilabilir[k]) {
            printf("P%d: kaynak su an yok, surec bekletiliyor\n", surec);
            return false;
        }
    }

    /* Geçici olarak ver ve güvenliği sına. */
    for (int k = 0; k < KAYNAK_TURU; k++) {
        tahsis[surec][k] += istek[k];
    }

    if (guvenli_mi(NULL)) {
        printf("P%d: istek karsilandi, sistem guvenli kaldi\n", surec);
        return true;
    }

    /* Güvensizse tahsis geri alınır; sistem hiçbir zaman güvensiz durumda bırakılmaz. */
    for (int k = 0; k < KAYNAK_TURU; k++) {
        tahsis[surec][k] -= istek[k];
    }
    printf("P%d: istek reddedildi, karsilanmasi sistemi guvensiz yapardi\n", surec);
    return false;
}

int main(void)
{
    int sira[SUREC_SAYISI];

    if (guvenli_mi(sira)) {
        printf("baslangic durumu guvenli, sira:");
        for (int i = 0; i < SUREC_SAYISI; i++) {
            printf(" P%d", sira[i]);
        }
        printf("\n");
    } else {
        printf("baslangic durumu GUVENSIZ\n");
    }

    const int istek_p1[KAYNAK_TURU] = {1, 0, 2};
    istek_yap(1, istek_p1);

    const int istek_p4[KAYNAK_TURU] = {3, 3, 0};
    istek_yap(4, istek_p4);

    const int istek_p0[KAYNAK_TURU] = {0, 2, 0};
    istek_yap(0, istek_p0);

    return 0;
}
