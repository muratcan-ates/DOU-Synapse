/*
 * fork_example.c — Süreç yaratma, wait() ve dosya tanımlayıcısı yönetimi örneği.
 *
 * Bu dosya DOĞRU bir örnektir (code_trace soru tipi için, T002): fork() ile bir çocuk
 * süreç yaratılır, ebeveyn wait() ile çocuğun bitmesini bekler ve paylaşılan dosya
 * tanımlayıcısı (fd) her iki süreçte de dikkatlice kapatılır (01-processes.md, "fork()
 * sonrası kapatılmayan fd" sızıntı uyarısına karşı doğru davranış).
 *
 * Derleme: gcc -o fork_example fork_example.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <fcntl.h>

int main(void) {
    int fd = open("ornek.txt", O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }

    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        close(fd);
        return 1;
    }

    if (pid == 0) {
        /* Çocuk süreç: fd, fork() sayesinde ebeveynden miras alındı (aynı dosyaya
         * yazar; dosya konumu (offset) da paylaşılır). */
        const char *msg = "cocuk surecten yazildi\n";
        write(fd, msg, 23);
        close(fd);          /* Çocuk kendi fd kopyasını kapatır. */
        _exit(0);
    }

    /* Ebeveyn süreç: pid > 0, çocuğun PID'sini içerir. */
    const char *msg = "ebeveyn surecten yazildi\n";
    write(fd, msg, 25);
    close(fd);               /* Ebeveyn de kendi fd kopyasını kapatır. */

    int status;
    pid_t finished = waitpid(pid, &status, 0);
    if (finished == pid && WIFEXITED(status)) {
        printf("cocuk surec %d, cikis kodu %d ile bitti\n", pid, WEXITSTATUS(status));
    }

    return 0;
}
