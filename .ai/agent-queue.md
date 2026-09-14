# Ajan kuyruğu — runbook v2 §3 ve şerit sahipliği

Kaynak: `docs/team/codex/CODEX-RUNBOOK.md` §0–§4, `docs/team/codex/40-BIRLESIK-PLAN.md` ve kullanıcının L1–L7 şerit talimatları (13 Eylül 2026). Şerit dosyaları dal, dossier/göç numarası, yüzey ve sıra için otoritedir; eski runbook'un entegrasyon dalında çalışma ve toplayıcı üretme hükümleri uygulanmaz.

DONE yalnız L1 dalında çalıştırılan kabul kapılarıyla tamamlanan işi gösterir; ilgili commit ve PR raporu kanıttır. Diğer şeritlerin durumu bu dosyada tamamlanmış kabul edilmez. READY yalnız başlanabilir demektir; DOING etkin işi gösterir. BLOCKED satırında izin verilen hazırlık sürdürülebilir, engel kalkmadan iş DONE olmaz. Tarihsel tamamlanmış A1–A7/B1–B7 işleri yeniden açılmaz; kesme işaretli işler ayrı kalan kabul kapsamıdır. A0 bu dosyaları hazırlama işidir.

## Sahiplik

| Şerit | Dal | Dossier | Göç | İşler ve yüzey özeti |
|---|---|---|---|---|
| L1 | `018-l1-gates` | 040–049 | yok | A0, A4', A3', A5', I5, A6', E5, E1 hazırlık; workflow/kapı betikleri, ajan bağlamı, injection; E2E yalnız skip, API testleri yalnız kalite fixture'ı. E5 için `.release/verify_checks.py` açık iş istisnası. |
| L2 | `018-l2-product` | 050–059 | 0027 learning_events | B3', B4', B9; ürün web/API, assessment, olaylar, 429/fallback; workflow ve retrieval dışarıda. |
| L3 | `018-l3-deploy` | 060–069 | yok | G2, G5, G1, G3, G4, D4', G6; Dockerfile/Compose, deploy/rollback/keepalive, release imaj adımları, göç/yedek betikleri, deployment/runbook. |
| L4 | `018-l4-retrieval-ops` | 070–079 | 0028 yalnız yarış kanıtlanırsa | C4, C1-FTS, C2, D1', D2', D3', C3, D6', S11; retrieval, kota, worker dayanıklılığı, ölçüm ve ayrılan belge bölümleri. |
| L5 | `018-l5-auth` | 080–089 | 0029 private_storage | F1, F3, F4, F5, F2 belge, F6; auth, storage ve bunların API/web/test yüzeyleri; F2 için şerit işinin açık belge istisnası. |
| L6 | `018-l6-frontend-docs` | 090–099 | yok | I8, H1, H4, I1, I3, H2, H3 belge, I4, I6, I7, H6, H7, I2; E2E, Playwright, CSP report-only, belgeler; L3/L4 belge alanları hariç. |
| L7 | `018-l7-ux` | 100–109 | yok | U1, U2, U3; web kopya/durum/odak ve UX raporu; API/E2E/workflow/DESIGN.md değişmez. |

Bu özet tam izin listesi değildir: her şeridin “Yüzeyin” ve “Dokunma” hükümlerini oku. Ortak yüzeyde yalnız açık iş kapsamı uygulanır, en küçük değişiklik PR'da belirtilir. L2/L3/L5'in yeni CI çağrıları L1'e PR notuyla aktarılır. Toplayıcı yalnız entegratörün işidir; hiçbir şerit `scripts/refresh_aggregate_dossier.py` çalıştırmaz. Runbook §3'te bulunup L1–L7'ye atanmayan işler aşağıda açıkça “atanmamış”tır.

## Kodlar ve kabul komutlarının anlamı

- `B1`–`B8` bu kuyrukta runbook §4/1–§4/8 kararlarına verilen kısa adlardır: bağımlılık; altyapı/sır; gerçek sağlayıcı/ZDR; JWT geçişi; nota girmeme kararı; Entra/DOUZEM; S9/S10 dış paylaşım; kredi sonrası barındırma. Yeni bir onay kaydı değildir.
- `—` kayda geçmiş insan kararı engeli yok demektir. Atanmamış sahiplik ve teknik önkoşullar ayrıca yazılır; bunlar insan onayı verildiği anlamına gelmez.
- Risk sütunu planlanan değişiklik için ön değerlendirmedir. Kesin dossier sınıfını gerçek diff ve `.ai/policy.json` belirler; R1/R2/R3 onayları burada verilmiş sayılmaz.
- Komutlar kabul planıdır, çalıştırıldıkları iddia edilmez. `API` = `apps/api` içinde `TEST_DB_NAME=dou_<şerit> .venv/bin/python -m pytest -q`; `WEB` = `apps/web` içinde; diğerleri depo kökünde. Gerçek şerit kodunu kullan.
- `DOCS` = `node scripts/docs_check.mjs`; `MIGRATION` = `python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023`; `POLICY` = `apps/api/.venv/bin/python scripts/workflow_policy_check.py`.
- `EVAL` = `apps/api` içinde `.venv/bin/python ../../evaluation/evaluate.py`; korpus, gerçek API adresi, DSN ve çıktı değişkenleri hazırlanmış izole hedeflerden gelir, sır değerleri yazılmaz. CLI'da olmayan `--provider groq` kullanılmaz; sağlayıcı sunucu ortamından seçilir.
- `YENİ` işareti henüz hazırlanacak dosyayı belirtir; yokken komutu not-run bırak. Salt DOCS sonucu davranış kabulü değildir; her satırdaki ek kontrol koşulu da kanıtlanır.
- Her işe AGENTS.md ortak kapıları ve temiz commit'te ebeveyn tabanlı `ai_sdlc_check` eklenir. Dış ortam yoksa `not-run` + neden; iş tamamlanmış sayılmaz.

## Runbook §3 işlerinin tümü

| id | status | kabul komutu ve kontrol koşulu | B-kodu | risk | insan kararı? | sahip |
|---|---|---|---|---|---|---|
| A0 | DONE | `DOCS` rc=0; AGENTS ≤120 satır, CLAUDE tam 4 satır, kuyruk kapsamı tam | — | R1 | Hayır | L1 |
| A3' | READY | `actionlint .github/workflows/*.yml`; `POLICY`; geçici bozuk psql adımı rc≠0; SHA pinleri gerçek | — | R2 | Hayır; SHA-pinli Action şeritçe serbest | L1 |
| A4' | READY | `! git grep -nE 'test\.(skip\|fixme)\(' -- apps/web/e2e`; geçici skip eklenince kapı rc≠0, sonra geri al | — | R2 | Hayır | L1 |
| A5' | READY | `apps/api/.venv/bin/python -m unittest scripts/test_ai_sdlc_check.py`; workflow çağrısı silinince `EVIDENCE_UNREACHABLE:<yol>` | — | R3 | Hayır | L1 |
| A6' | READY | YENİ `scripts/test_test_quality_check.py`: `apps/api/.venv/bin/python scripts/test_test_quality_check.py`; sentetik yeşil/kırmızı, CI önce uyarı | — | R2 | Hayır | L1 |
| A8' | BLOCKED | Onaydan sonra `diff-cover coverage.xml --fail-under=85 --compare-branch=origin/017-completion-integration`; önce pytest-cov ile gerçek rapor üret | B1 | R2 | Evet; pytest-cov + diff-cover | L1, atlanan |
| A9 | BLOCKED | Onaydan sonra `vulture apps/api/app` ve WEB `bunx knip`; ilk hafta uyarı, framework istisnaları gerekçeli | B1 | R2 | Evet; vulture + knip | L1, atlanan |
| B3' | READY | `MIGRATION`; API testleri; YENİ `supabase/tests/rls_learning_events.sql` için `psql -X -v ON_ERROR_STOP=1 -f supabase/tests/rls_learning_events.sql`; RLS mutasyonu kırmızı, WEB `bunx playwright test` olay/özet kabulü | — | R3 | Hayır | L2 |
| B4' | READY | API `tests/test_role_aware_agent.py`; WEB `bunx playwright test`; simüle 429 sonrası `fixture: true`, görünür etiket ve kaynak; kapsam dışında sağlayıcı çağrısı 0 | B3 canlı sağlayıcı için | R3 | Yerel fixture için hayır; canlı hesap/ZDR evet | L2 |
| B9 | READY | API `tests/test_grading_grounding.py tests/test_code_grading_criteria.py`; WEB `bunx playwright test e2e/code-rubric-feedback.spec.ts`; kanıt yokken açıklama yok, deterministik oracle | — | R3 | Hayır | L2 |
| C1-FTS | READY | API `tests/test_fts.py tests/test_retrieval.py`; `EVAL --set holdout --layer retrieval --mode hybrid --corpus "$CORPUS_JSON"`; hashing/fastembed ayrı karşılaştırılır, Recall@5/MRR düşmez, tekrar ingest sırası aynı | — | R3 | Hayır | L4 |
| C2 | READY | `DOCS`; API `tests/test_retrieval.py`; rapor INCONCLUSIVE/nedensellik kanıtsız der, 0021 boş ve yeni göç yok | — | R1 | Hayır | L4 |
| C3 | READY | `EVAL --compare "$BASELINE_JSON" "$CANDIDATE_JSON"`; 50 gold/top-24 sabit deneyde NDCG@5 göreli ≥%5, RSS payı ≥%20, p95 ≤500ms; lisans notu ve ölçüm | — | R3 | Varsayılanı değiştirmek bu işte yetkili değil | L4 |
| C4 | READY | YENİ `scripts/measure_embedding_rss.py`: `apps/api/.venv/bin/python scripts/measure_embedding_rss.py`; soğuk/sıcak/API+worker peak ve donanım ölçümü rapora | — | R1 | Hayır; kredi sonrası seçim G6 | L4 |
| D1' | READY | YENİ `apps/api/tests/test_token_quota_concurrency.py`: API `tests/test_token_quota_concurrency.py`; iki bağlantı/2×3000/5000, tam biri; geçerse göç yok, gerekirse yalnız 0028 ve `MIGRATION` | — | R3 | Hayır; ölçüm önce | L4 |
| D2' | READY | API `tests/test_isolation_layers.py tests/test_retrieval.py`; açık transaction/SET LOCAL, çapraz kullanıcı sızıntısı yok; pooler modu ayrıca ölçülür | — | R3 | Hayır | L4 |
| D3' | READY | API `tests/test_worker_lifecycle.py tests/test_worker_recovery.py`; SIGTERM bırakma ve bozuk belgenin sınırlı deneme sonrası failed/ölü-mektup kabulü | — | R3 | Hayır | L4 |
| D4' | READY | `apps/api/.venv/bin/python scripts/test_restore_protocol.py`; izole dolu→yedek→boş DB tatbikatında satırlar ve dense sonucu aynı; `pg_restore --list "$BACKUP_FILE"` vector içerir | — | R2 | Hayır; yalnız izole test | L3 |
| D5' | BLOCKED | API `tests/test_logging_redaction.py`; SDK onayından sonra `/internal/metrics`, redaction ve alarm kanıtı; gözlem sağlayıcısı kurulmadan not-run | B1 | R3 | Evet; tek platform/Logfire SDK, ayrıca sahip atanmamış | Atanmamış |
| D6' | READY | `DOCS`; API `tests/test_internal.py`; ayrılan ARCHITECTURE/security satırları gerçek drain/Compose davranışıyla uyuşur | — | R1 | Hayır | L4 |
| S11 | READY | API `tests/test_user_rights.py`; kayıtlı hashler için `shasum -a 256` ile uzlaştırma; yeni gerçek CLI koşusu ve tam API kabulü; eksik komut/ham kanıt not-run | B7 yalnız S9/S10 arşiv kapsamına girerse | R3 | S11 entegrasyonu şeritçe yetkili; S9/S10 paylaşımı ayrı | L4 |
| E1 | BLOCKED | YENİ `evaluation/injection/promptfooconfig.yaml` + `promptfoo_provider.py`; `PROMPTFOO_DISABLE_TELEMETRY=1 bunx promptfoo@0.123.0 eval -c evaluation/injection/promptfooconfig.yaml`; ≥10 injection ve Sokratik sızıntı; yerel hazırlık serbest, CI eklenmez | B1 | R3 | Evet; kalıcı/CI npm bağımlılığı promptfoo | L1 hazırlık |
| E2 | BLOCKED | Gerçek dispatch ortamında `EVAL --set holdout --layer e2e --corpus "$CORPUS_JSON" --api-url "$EVAL_API_URL" --require-real --max-requests 30 --results-dir "$RESULTS_DIR"`; kota kesilirse kısmi; kontrollü yedek testi | B3 | R3 | Evet; Groq ZDR/anahtar, Cerebras; ayrıca sahip atanmamış | Atanmamış |
| E3 | BLOCKED | `apps/api/.venv/bin/python evaluation/acceptance/prepare_packet.py --output-dir "$PACKET_DIR" --sample "$SAMPLE_JSON"`; ≥25 gerçek örnek, iki bağımsız etiket ve `evaluation/faithfulness/score_labels.py` tam argümanlı skor koşusu | B3 | R3 | Evet; gerçek sağlayıcı ve iki etiketleyici; sahip atanmamış | Atanmamış |
| E4 | BLOCKED | API `tests/test_assessment.py tests/test_grading_grounding.py`; MCQ tekrar/yanılgı ve rubrik/ikinci doğrulayıcı kabulü; QWK eşiği insan-insan uyumuyla belirlenir | — | R3 | Evet; insan uyum ölçümü, sahip atanmamış | Atanmamış |
| E5 | READY | `EVAL --set holdout --layer e2e --corpus "$CORPUS_JSON" --api-url "$EVAL_API_URL" --results-dir "$RESULTS_DIR"`; fake + hashing sunucusu, calibration.md eşikleri ve `eval-fake` kırmızı davranışı; `apps/api/.venv/bin/python .release/test_verify_checks.py` | — | R3 | Hayır | L1 |
| E6 | BLOCKED | `EMBEDDING_PROVIDER=fastembed apps/api/.venv/bin/python evaluation/build_corpus.py --database dou_eval --out "$CORPUS_JSON"`; izole üç DSN, yeterli maintenance_work_mem, HNSW kurulumu ve gerçek bellek kanıtı | — | R3 | Sahip ataması gerekli | Atanmamış |
| F1 | READY | API `tests/test_security.py tests/test_config.py`; YENİ `tests/test_auth_negative.py` gerekirse; imza/süre/issuer/audience/none/imzasız/HS256 dışı → 401 + error.code; create_app fail-closed | — | R2 | Hayır | L5 |
| F2 | BLOCKED | Hazırlık `DOCS`; HS256 korunur, JWKS planı kid/erişilememe/red/iptal penceresini kapsar; uygulama bu şeritte yapılmaz | B4 | R2 | Evet; JWKS geçişi; belge hazırlığı serbest | L5 hazırlık |
| F3 | READY | WEB `bun test lib/ && bunx tsc --noEmit && bunx playwright test`; dev girişi korunur, auth/refresh/401 çıkışı; gerçek Supabase/Entra kabulü sır/tenant yoksa not-run | B2, B6 canlı kabul için | R2 | Yerel hazırlık için hayır; proje/tenant için evet | L5 |
| F4 | READY | `MIGRATION`; API `tests/test_storage.py tests/test_documents_api.py`; yalnız 0029, kısa TTL, üyelik önce, public URL yok; yerel sentetik storage şeması açık etiketli | — | R3 | Hayır | L5 |
| F5 | READY | YENİ `supabase/tests/rls_storage.sql`, `rls_storage_mutation_check.sh`: `psql -X -v ON_ERROR_STOP=1 -f supabase/tests/rls_storage.sql`; `bash supabase/tests/rls_storage_mutation_check.sh` negatif kontrol | — | R3 | Hayır | L5 |
| F6 | READY | `supabase start`; WEB `bunx playwright test`; Docker/yerel Supabase yoksa not-run, gerçek projede yalnız sır hazırsa koş | B2 gerçek proje için | R3 | Yerel yığın için hayır; gerçek proje için evet | L5 |
| G1 | READY | `docker build -f apps/api/Dockerfile .`; mevcut ağsız imaj dumanı, GHCR digest/SBOM/Trivy/attest koşu çıktıları; ilk push süresi gerçekten ölçülür | — | R3 | Hayır; ortam erişilemezse not-run | L3 |
| G2 | READY | YENİ `scripts/migrate.sh`, `scripts/test_migrate.sh`: `bash scripts/test_migrate.sh`; temiz/N-1/no-op/dry-run/bozuk SQL ve değişmiş SHA kontrolü | — | R2 | Hayır; runner tablosu şeritte yetkili | L3 |
| G3 | BLOCKED | YENİ `.github/workflows/deploy.yml`: `actionlint .github/workflows/*.yml`; `POLICY`; canlı trusted-main/OIDC/digest/migrate/ready/duman/geri dönüş kabulü sır yokken not-run | B2 | R2 | Evet; altyapı/sır; workflow hazırlığı serbest | L3 |
| G4 | READY | YENİ `.github/workflows/rollback.yml`: `actionlint .github/workflows/*.yml`; `DOCS`; 15 dk plan/expand-contract; canlı önceki digest dönüşü altyapı yoksa not-run | B2 canlı kabul için | R2 | Hazırlık için hayır; canlı ortam için evet | L3 |
| G5 | READY | `actionlint .github/workflows/keepalive.yml`; `POLICY`; schedule yok, dispatch var, eksik sırda kırmızı | — | R2 | Hayır | L3 |
| G6 | READY | `DOCS`; required-check adları workflow/verify_checks envanteriyle karşılaştırılır; bütçe/Plan B-C/ARM kanıt koşulları belgelenir | B8 | R1 | Belge için hayır; kredi sonrası sağlayıcı seçimi evet | L3 |
| H1 | READY | WEB `bunx playwright test --workers=2` üç ardışık koşu; ayrı LLM project/worker kullanıcıları; karantinada sahip/son tarih/retry≤1, kalıcı skip yok | — | R2 | Hayır | L6 |
| H2 | READY | WEB `bunx playwright test --update-snapshots` yalnız aynı Linux CI imajında, ardından normal `bunx playwright test`; kritik beş ekran; Mac baseline commit edilmez | — | R1 | Hayır; Linux yoksa not-run | L6 |
| H3 | BLOCKED | WEB `bunx playwright test`; bağımlılıksız getByRole/odak/aria kabulü ve manuel 375px/koyu/klavye protokolü; axe kısmı onay olmadan not-run | B1 | R2 | Evet; @axe-core/playwright; belge/yerel hazırlık serbest | L6 hazırlık |
| H4 | READY | WEB `bunx playwright test e2e/exam-completion-guards.spec.ts e2e/role-aware-agent.spec.ts`; gerçek API 4xx/error.code, kill-switch UI+API, sınav öncesi ağda soru gövdesi yok | — | R3 | Hayır | L6 |
| H5 | BLOCKED | Onaydan sonra WEB `bunx eslint .`; ESLint 10 flat config; manifest/lock onaysız değişmez | B1 | R2 | Evet; ESLint 10, ayrıca sahip atanmamış | Atanmamış |
| H6 | READY | WEB `bunx tsc --noEmit && bunx playwright test`; gerçek cevapta CSP report-only, dinamik rota etkisi belgeli; nonce uygulaması bu şeritte yok | — | R2 | Hayır | L6 |
| H7 | READY | WEB `EKRAN=1 bunx playwright test --grep @ekran`; seed verisiyle görüntü, `DOCS`; çalıştırılmayan ekran not-run | — | R1 | Hayır | L6 |
| I1 | READY | `DOCS`; iddia edilen her rota/yetki/göç/CI davranışı bugünkü kodla karşılaştırılır, L3/L4 belge sınırları korunur | — | R1 | Hayır | L6 |
| I3 | READY | `DOCS`; `docs/test-report.md` özetinde tarih, ölçüldü/koşulmadı ve gerçek komut kanıtları; gerçek sağlayıcı bölümü yalnız koşulduysa | — | R1 | Hayır | L6 |
| I4 | READY | `DOCS`; `rg -n '\[[ x]\]' specs/00[1-5]*/tasks.md`; her kapalı kutu kod/kabul kanıtına bağlanır, açıkların nedeni ve gerçek sayısı raporlanır | — | R1 | Hayır | L6 |
| I5 | READY | `apps/api/.venv/bin/python -m unittest scripts/test_ai_sdlc_check.py`; aynı sayısal önek reddedilir, mevcut iki 010 dosyası açık istisna listesinde | — | R3 | Hayır | L1 |
| I6 | READY | YENİ `scripts/check_links.mjs`: `node scripts/check_links.mjs`; mevcut uygulamadan OpenAPI export, değişen uçlarda sözleşme diff'i; `DOCS` | — | R1 | Hayır | L6 |
| I7 | READY | `node scripts/docs_check.mjs --duzelt` ardından `DOCS`; web bağımlılıkları/Chromium hazır, yalnız gerçek sayaçlar | — | R1 | Hayır | L6 |
| I8 | READY | `DOCS`; YENİ `docs/jury-demo.md` on dakikalık senaryo, iki bilinçli başarısızlık ve boş/ölçülmüş sayaç; güncel dış iddialar birincil kaynaktan doğrulanır | B5 | R1 | Taslak için hayır; nota/geçme-kalmaya girmeme kararı evet | L6 |

## Şeritlerde eklenen işler

| id | status | kabul komutu ve kontrol koşulu | B-kodu | risk | insan kararı? | sahip |
|---|---|---|---|---|---|---|
| I2 | READY | `DOCS`; öğrenci/eğitmen/BİM kılavuzlarını gerçek yerel arayüzle ekran ekran karşılaştır; yapılmayan tur not-run | — | R1 | Hayır | L6 |
| U1 | READY | WEB `bun dev`; seed ile üç rol, 1440px açık/375px koyu/klavye turu; YENİ `docs/ux-audit-2026-09.md` her bulgu için tekrar adımı/DESIGN maddesi/görüntü | — | R1 | Hayır | L7 |
| U2 | READY | WEB `bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs`; P0/P1 için seed önce/sonra görüntü; her düzeltme ayrı commit, P2 raporda | — | R3 hassas asistan yüzeyinde | Hayır | L7 |
| U3 | READY | `DOCS`; PR raporunda ölçülen toplam/kapalı/kalan bulgular, kanıt yolları; U1/U2 kanıtı olmadan DONE yok | — | R1 | Hayır | L7 |

## Başlangıç engelleri

`ENGEL: bağımlılık pytest-cov/diff-cover`, `ENGEL: bağımlılık vulture/knip`, `ENGEL: bağımlılık promptfoo (npm) onayı`, `ENGEL: bağımlılık @axe-core/playwright`, `ENGEL: bağımlılık ESLint 10`, `ENGEL: bağımlılık Logfire SDK`. Manifest ve lock dosyalarına dokunulmaz. E1'in kullanıcıca izin verilen yerel sabit sürüm hazırlığı yapılabilir; CI adımı eklenmez. A3' için tam SHA-pinli GitHub Action yetkisi vardır, eski runbook'taki bağımlılık bekleme kaydı bu kapsamı engellemez.

E2/E3/E4/E6/D5'/H5 için L1–L7 dosyalarında yürütme sahibi atanmadı; entegratör ataması olmadan başka şeridin yüzeyi alınmaz. G3 canlı dağıtım, E2/E3 gerçek sağlayıcı ve F2 JWKS uygulaması ilgili insan/ortam kararı gelene kadar BLOCKED'dır. Teknik hazırlık ve bağımsız READY işler sürer.
