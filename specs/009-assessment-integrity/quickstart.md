# Yerel Doğrulama Quickstart

1. Diskte en az 10 GiB boş alan doğrula; bağımlılık cache'i indirme.
2. Benzersiz `dou_synapse_assessment_integrity_<pid>` test DB'si oluştur.
3. `0001..0016` migration'larını sırayla uygula.
4. Hedefli assessment/grading testlerini fake provider ile çalıştır.
5. RLS referans ve her bağımsız mutation koşusunu ayrı DB'de çalıştır.
6. Tam backend, Ruff/format, mypy ve OpenAPI drift kapılarını çalıştır.
7. Varsa frontend tip/helper testlerini; sonra tek worker gerçek-API Playwright'ı çalıştır.
8. Bütün geçici DB/API/browser süreçlerini kapat ve disk kalıntısını yeniden ölç.
9. Evidence raporunda yalnız sayılar/komut/commit kimliği tut; prompt, cevap, secret
   veya öğrenci içeriği kaydetme.

Yerel `fake-provider PASS`, staging/real-provider/production kanıtı değildir.

