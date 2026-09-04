# Hocanın kabul paketi

Bu paket kaynak bütünlüğü ve insan değerlendirmesi hazırlığıdır. Sahte sağlayıcı,
önbellek ve kaynak yetersizliği nedeniyle sağlayıcı çağrılmadan verilen ret,
gerçek model cevabının kaynak doğruluğunu veya öğretim kalitesini kanıtlamaz.
Materyaller ekip üretimi İşletim Sistemleri örnekleridir; hocanın gerçek materyal
ve puanlama onayı henüz alınmadı. Mevcut metinli örnekler için OCR gerekmedi.

## Çevrimdışı hazırlık

`apps/api` içinden `uv run python ../../evaluation/acceptance/prepare_packet.py
--output-dir /tmp/dou015-kabul-01` çalıştırılır. Kaynak ve goldset SHA256 özeti,
beş değerlendirme biçiminin insan çıpası taslağı ve açık kabul kapıları hazırlanır.
Hiçbir sağlayıcı veya API çağrılmaz. Var olan dizinin üzerine yazılmaz.

`assessment_cases.json` mevcut `SourceSpec` ve `RubricItem` tiplerini kullanır.
Öğretmen doğru/kısmi/yanlış örneklerini, kabul edilen ifadeleri, kaynak bölümünü,
rubriği ve beklenen puanı onaylar. Boş insan puanı otomatik doldurulmaz.
MCQ/kısa cevapta deterministik doğruluk ile açık/kod/hata inceleme sorularının
LLM değerlendirmesi ayrı raporlanır. Bu dilimde gerçek grading runner koşulmadı.

## Gerçek koşudan önce

1. Temiz ve commit edilmiş aynı aday SHA, ayrı yerel eval veritabanı ve ayrı
   değerlendirme anahtarı kullanılır. `EVAL_RUNTIME_ENABLED`, `EVAL_LLM_PROVIDER`,
   `EVAL_LLM_API_KEY`, `EVAL_RUNTIME_SECRET` yalnız eval sunucusunda ayarlanır.
2. Korpus kurucuya `--admin-dsn`, `--app-dsn`, `--worker-dsn` verilir (veya
   `EVAL_ADMIN_DSN`, `EVAL_APP_DSN`, `EVAL_WORKER_DSN`). Üç bağlantı aynı yerel
   veritabanı/porta; uygulama ve işçi kendi önceden açılmış LOGIN rollerine gitmelidir.
   Kurucu paylaşılan rol parolalarını veya başka geliştirme veritabanını değiştirmez. Yeni corpus
   manifesti parola içermez. Retrieval için `--database-url` ayrıca verilir.
3. API yalnız loopback adresinde açılır. Harness `EVAL_RUNTIME_SECRET` ile gerçek
   runtime/yanıt kanıtını alır; yönlendirmeleri izlemez. Serbest `--llm-note`
   gerçeklik kanıtı değildir. SHA, temiz çalışma ağacı, runtime/koşu/yapılandırma,
   gövde özeti ve gerçek transport çağrısı eşleşmezse gerçek kabul durur.
4. `faithfulness/pull_sample.py --corpus /tmp/corpus.json --api-url
   http://127.0.0.1:8015 --require-real --output-dir /tmp/dou015-faithfulness-01
   --max-requests 30` ile 25 cevap alınır. Kota/erişim veya HTTP bütçesi koşuyu
   durdurur; aynı output-dir ile yalnız tamamlanmamış vakalara devam edilir.
   Bütçe HTTP istek sayısıdır; modelin iç retry/fallback denemeleri receipt.calls
   ile ayrıca sayılır. Tamamlanmış form ve sonuçların üzerine yazılmaz.
5. `evaluate.py --set holdout --layer e2e ... --require-real --max-requests 30`
   ve `injection/run_injection.py ... --require-real --output-dir ...` mevcut
   kapsam/Sokratik/injection vakalarını çalıştırır. Kapsam retleri ve önbellek
   cevapları ayrı sayılır; gerçek cevap kalitesi örneklemine alınmaz.

## İnsan değerlendirmesi

İki kişi aynı örneklemin ayrı `labels_etiketleyici_1.md` ve
`labels_etiketleyici_2.md` dosyalarını birbirinden bağımsız doldurur. Mevcut
`evaluation/faithfulness/score_labels.py` ile `--sample`, `--first`, `--second`,
`--labeler-1`, `--labeler-2`, `--attest-independent`, `--json-out` ve
`--adjudication-out` kullanılır. Araç gerçek runtime/yanıt kanıtını, 20-30 cevap,
etiket tamlığı ve bağımsız kişi adlarını doğrular; tartışma öncesi ham uyum ve
Cohen kappa hesaplar. Etiketleri veya insan onayını araç üretmez.

Kaynak doğruluğuna ek olarak Sokratik yanıtta doğrudan çözüm sızıntısı,
puanlamada rubrik uyumu ve “neden yanlış?” alıntısının çelişkiyi gerçekten
anlatması öğretmen tarafından incelenir. Otomatik işaret bulunmaması başarı
anlamına gelmez. Son kabul için gerçek koşu, iki bağımsız inceleme ve öğretmen
kararı aynı aday/kaynak özetine bağlanır; canlı hizmet/backup/rollback kanıtı
ayrı yayın kapısıdır.
