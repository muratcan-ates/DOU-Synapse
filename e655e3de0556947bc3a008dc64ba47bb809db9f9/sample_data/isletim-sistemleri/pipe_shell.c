/*
 * İki komutu boru ile bağlayan küçük bir kabuk parçası: "cmd1 | cmd2".
 *
 * DOĞRU örnek (code_trace). Kavramsal anlatım 13-ipc.pptx ve 01-processes.pdf içinde.
 *
 * İzlenmesi istenen nokta: hangi süreç hangi boru ucunu kapatıyor ve neden.
 * Kapatılmayan tek bir yazma ucu, okuyan tarafın dosya sonu görmemesine ve
 * programın süresiz beklemesine yeter.
 *
 * Derleme:  cc -std=c11 -Wall -Wextra -o pipe_shell pipe_shell.c
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

/*
 * Boru dizisinin uçları:
 *   boru[0] = okuma ucu
 *   boru[1] = yazma ucu
 * Bu sıra pipe(2) tarafından sabitlenir ve karıştırılması sessiz bir kilitlenme üretir.
 */
#define OKUMA_UCU 0
#define YAZMA_UCU 1

static void hata_ver(const char *nerede)
{
    perror(nerede);
    _exit(EXIT_FAILURE);
}

/*
 * sol  -> standart çıktısı boruya yazar
 * sag  -> standart girdisini borudan okur
 *
 * Dönen değer sağdaki komutun çıkış kodudur; kabukların boru hattı için
 * raporladığı değer varsayılan olarak budur.
 */
static int boru_hatti_calistir(char *const sol[], char *const sag[])
{
    int boru[2];

    if (pipe(boru) == -1) {
        perror("pipe");
        return -1;
    }

    pid_t sol_pid = fork();
    if (sol_pid == -1) {
        perror("fork");
        close(boru[OKUMA_UCU]);
        close(boru[YAZMA_UCU]);
        return -1;
    }

    if (sol_pid == 0) {
        /* Sol çocuk: yazar. Okuma ucuna hiç ihtiyacı yok, hemen kapatılır. */
        close(boru[OKUMA_UCU]);

        /* Standart çıktı boruya yönlendirilir. */
        if (dup2(boru[YAZMA_UCU], STDOUT_FILENO) == -1) {
            hata_ver("dup2 (sol)");
        }
        /* dup2 sonrası özgün tanıtıcı gereksizdir; açık kalırsa fazladan bir
         * yazma ucu daha yaşar ve okuyan taraf EOF göremez. */
        close(boru[YAZMA_UCU]);

        execvp(sol[0], sol);
        hata_ver("execvp (sol)");
    }

    pid_t sag_pid = fork();
    if (sag_pid == -1) {
        perror("fork");
        close(boru[OKUMA_UCU]);
        close(boru[YAZMA_UCU]);
        waitpid(sol_pid, NULL, 0);
        return -1;
    }

    if (sag_pid == 0) {
        /* Sağ çocuk: okur. Yazma ucunu kapatmazsa, sol komut bitse bile
         * borunun bir yazma ucu açık kalır ve read() süresiz bloke olur. */
        close(boru[YAZMA_UCU]);

        if (dup2(boru[OKUMA_UCU], STDIN_FILENO) == -1) {
            hata_ver("dup2 (sag)");
        }
        close(boru[OKUMA_UCU]);

        execvp(sag[0], sag);
        hata_ver("execvp (sag)");
    }

    /*
     * Ebeveyn her iki ucu da kapatmak ZORUNDADIR. Ebeveynde açık kalan bir yazma
     * ucu, sol komut bitse dahi sağ komuta EOF gelmemesine yol açar; program
     * kilitlenmiş gibi görünür ve sebebi kodun hiçbir yerinde hata olarak
     * raporlanmaz.
     */
    close(boru[OKUMA_UCU]);
    close(boru[YAZMA_UCU]);

    int sol_durum = 0;
    int sag_durum = 0;
    /* Her iki çocuk da toplanır; toplanmayan çocuk zombi olarak kalır. */
    while (waitpid(sol_pid, &sol_durum, 0) == -1 && errno == EINTR) {
        continue;
    }
    while (waitpid(sag_pid, &sag_durum, 0) == -1 && errno == EINTR) {
        continue;
    }

    return WIFEXITED(sag_durum) ? WEXITSTATUS(sag_durum) : EXIT_FAILURE;
}

int main(void)
{
    char *const sol[] = {"ls", "-1", NULL};
    char *const sag[] = {"wc", "-l", NULL};

    int cikis = boru_hatti_calistir(sol, sag);
    if (cikis == -1) {
        return EXIT_FAILURE;
    }
    printf("boru hatti bitti, cikis kodu %d\n", cikis);
    return cikis;
}
