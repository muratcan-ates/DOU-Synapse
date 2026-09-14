# Jüri Demo Senaryosu — 14 Eylül 2026

## Senaryo hedefi
P5 kapsamındaki jüri akışını canlı yürütecek şekilde, 10 dakikalık prova adımlarını ve ölçümleri üretmek.

## Çalıştırma durumu
- 14.09.2026: demo stack açma/koşturma ve bütün adımlar **KOŞULMADI**.
- Son girişimde teknik engel: bu ortamda `docker` bulunmadı, bu yüzden demo yığını (`docker compose ...`) ayağa kaldırılamadı.

## Denenen ölçümler
1. `pg_isready -h /tmp -p 5432 -U postgres` → **KOŞULMADI** (`/tmp` soketi için yanıt yok).
2. `psql` ile `SELECT 1` denemesi → **KOŞULMADI** (`Operation not permitted`).
3. `curl http://localhost:8030/health/ready` → **KOŞULMADI** (yanıt yok).
4. `docker compose up -d db api api-fallback` → **KOŞULMADI** (`docker: command not found`).

## Planlanan 10 dakikalık adımlar (saha notu)
- Eğitmen yükleme
- Soru üretme/onaylama/yayımlama
- Öğrenci konu seçimi
- Süreli çözüm
- Yanlış cevapta kaynak kartı
- İlerleme ekranı
- Prova süresi ölçümü

Hepsinin ölçümleri yukarıdaki teknik engel nedeniyle **koşulmadı**.

## ENGEL
- Ortam başlangıç engeli: demo için gerekli servisleri çalıştıracak `docker` binary'si bu oturumda yüklü değil; API/PostgreSQL ayakta olmayınca ekran görüntüsü üretimi ve senaryo koşumu yapılamadı.
