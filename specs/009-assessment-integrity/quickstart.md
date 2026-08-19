# Yerel Doğrulama Quickstart

1. Diskte en az 10 GiB boş alan doğrula; bağımlılık cache'i indirme.
2. Benzersiz `dou_synapse_assessment_integrity_<pid>` test DB'si oluştur.
3. `0001..0016` migration'larını sırayla uygula; ardından yalnız yerelde
   `supabase/local_dev_setup.sql` ile `dou_api_runtime`/worker LOGIN'lerini aç.
   `dou_app` NOLOGIN kalmalıdır.
4. Uygulamanın kullandığı DSN'de `session_user`, `current_user` ve
   `app.is_api_runtime()` değerlerini doğrula; beklenen sonuç runtime/runtime/true.
5. Varsayılan `ASSESSMENT_BLUEPRINT_ENABLED=false` kalsın; yalnız bu kontrollü yerel
   assessment koşusu için açıkça `true` ver. Hedefli assessment/grading testlerini
   fake provider ile çalıştır.
6. RLS referans, upgrade/backfill ve her bağımsız mutation koşusunu ayrı DB'de çalıştır.
   Upgrade çıktısında `upgrade_backfill__tum_cohort_en_gec_expiry_sinirinda`,
   `upgrade_mixed_use__yalniz_legacy_oturum_sahibi_devam_eder`,
   `upgrade_mixed_use__yeni_ogrenci_resmi_soruyu_goremez` ve
   `upgrade_defaults__tum_owner_grantleri_ve_public_execute_temiz` PASS olmalıdır. Rol kesimi
   yarışını yalnız kontrollü yerel DB'de şu opt-in ile doğrula:
   `ASSESSMENT_PREFLIGHT_ALLOW_ROLE_MUTATION=1 PG_BIN=/opt/homebrew/opt/postgresql@16/bin supabase/tests/assessment_runtime_preflight_check.sh`.
7. Tam backend, Ruff/format, mypy ve OpenAPI drift kapılarını çalıştır.
8. Varsa frontend tip/helper testlerini; sonra tek worker gerçek-API Playwright'ı çalıştır.
9. Bütün geçici DB/API/browser süreçlerini kapat ve disk kalıntısını yeniden ölç.
10. Evidence raporunda yalnız sayılar/komut/commit kimliği tut; prompt, cevap, secret
   veya öğrenci içeriği kaydetme.

Yerel `fake-provider PASS`, staging/real-provider/production kanıtı değildir.

Mevcut bir yerel DB'yi `0016`ya yükseltirken temiz kurulum döngüsünü taklit etmeyin:
önce runtime LOGIN/üyeliğini hazırla; API'yi durdur; admin bağlantısında ayrı commit
olarak `ALTER ROLE dou_app NOLOGIN PASSWORD NULL` uygula; eski login'in reddedildiğini
ve `pg_stat_activity` içinde `dou_app` oturumu kalmadığını doğrula; sonra `0016`yı
uygula. Migration bu ön kesimi assert eder, ilk kez kendisi yapmaz. Ayrıca `dou_app`
parent rolünü, runtime üyelerini/parent'larını, cross-owner tablo grant'lerini ve ilgili
function owner'ların global/schema-local PUBLIC EXECUTE varsayılanlarını denetler;
gerekli default privilege'ları değiştiremeyen bir DB kimliğiyle bu kapıyı bypass etme.
Karma kullanılan eski soruların resmî kökü yerinde kalır;
legacy oturum dizisi/cevap kimliği değişmez ve yalnız oturum sahibi dar devam
istisnasından yararlanır. Yeni practice seçimi assessment satırını seçemez.
