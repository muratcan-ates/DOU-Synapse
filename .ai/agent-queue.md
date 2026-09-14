# Ajan iş kuyruğu

`docs/team/codex/CODEX-RUNBOOK.md` §3'teki **kalan** işlerin tek listesi. Kurallar `AGENTS.md`'de.
Tamamlanmış işler (§1'de sayılanlar) buraya girmez; kanıt `specs/018-codex-production-line/verification.md`.

**Durum:** `READY` alınabilir · `DOING` 13 Eylül 2026'da `024-autonomous-completion` dalında paralel
şerit olarak çalışılıyor (başka oturum almaz) · `DONE` kapandı · `BLOCKED` §4'teki insan kararına bağlı.

**Kabul komutu:** işin bittiğini kanıtlayan komut/koşul. `<oturum>` = şeride ayrılmış `TEST_DB_NAME`.
Kapıların tamamı her işte geçerlidir (`AGENTS.md` §5); bu sütun o işe **özgü** olanı yazar.

**B-kodu:** ⛔ = onaysız eklenemeyecek bağımlılık/lisans (bkz. §4/1). **Risk:** `.ai/policy.json`
sınıflandırması; `—` = policy.json'da hassas yol değil (yine de dokunulan başka hassas yol varsa dossier şarttır).

**İnsan kararı:** runbook §4 madde numarası. §4/7 (S9/S10 kod + sentetik kanıt arşivi paylaşım onayı)
gelene kadar o içerik sınıfında yeni push yoktur; diğer işler sürer.

## FAZ A' — Kapı hijyeni

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| A0 | DOING | `node scripts/docs_check.mjs` rc=0 | — | — | — |
| A3' | BLOCKED | `actionlint` rc=0; bilerek bozulmuş `psql` adımı kırmızı yanar (negatif kanıt) | ⛔ actionlint, zizmor | R2 (`.github/workflows/security.yml`) | §4/1 |
| A4' | DOING | `! git grep -nE 'test\.(skip\|fixme)\(' -- apps/web/e2e` rc=0; bilerek eklenen skip kapıyı kırar | — | R2 (`.github/workflows/ci.yml`) | — |
| A5' | DOING | `python3 -m unittest scripts/test_ai_sdlc_check.py`; bir workflow çağrısı silinince validator kırmızı | — | R3 (`scripts/ai_sdlc_check.py`) | — |
| A6' | DOING | `apps/api/.venv/bin/python scripts/test_quality_check.py` (yeni dosya); bozuk fixture'da rc≠0 | — | R2 (`.github/workflows/ci.yml`) | — |
| A8' | BLOCKED | `diff-cover --fail-under=85 --compare-branch=origin/017-completion-integration` rc=0 | ⛔ pytest-cov, diff-cover | R2 (`ci.yml`, `apps/api/pyproject.toml`) | §4/1 |
| A9 | BLOCKED | `vulture` / `knip` uyarı modunda rc=0; FastAPI dekoratörleri ve Next rotaları beyaz listede | ⛔ vulture, knip | R2 (workflow) | §4/1 |

## FAZ B' — Ürün: jüri Gün-1 çekirdeği

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| B3' | DOING | `python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023` PASS; `supabase/tests` mutasyon betiği kırmızı yanar; eğitmen özeti ucu + ekranı çalışır | — | R3 (`supabase/migrations/**`) | — |
| B4' | DOING | `cd apps/web && ./node_modules/.bin/playwright test` — "önceden kaydedilmiş demo yanıtı" etiketi görünür; kapsam dışı soruda LLM çağrısı 0 | — | R3 (`apps/web/components/course-assistant/**`) | §4/3 |
| B9 | READY | E2E: açık uçlu/kod cevabında çelişen kaynak parçası + sonraki ipucu var, kanıt yoksa açıklama üretilmiyor; `code_trace`/`bug_hunt` deterministik oracle testi ≥1 | — | R3 (`apps/api/app/modules/assessment/**`) | — |

## FAZ C' — Retrieval

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| C1-FTS | DOING | hashing ve E5 holdout Recall@5/MRR **düşmez**; iki ingest aynı sırayı üretir (`evaluation/evaluate.py`) | — | R2 (`apps/api/app/modules/retrieval/**`) | — |
| C2 | READY | `node scripts/docs_check.mjs` rc=0 — `docs/test-report.md`'de anomali notu; göç eklenmez, `0021` boş kalır | — | — | — |
| C3 | READY | 50 gold sorgu, top-24 sabit: NDCG@5 ≥ %5 göreli **ve** RSS payı ≥ %20 **ve** p95 ≤ 500 ms; geçmezse varsayılan olmaz | ⛔ jina-reranker-v2 lisansı CC-BY-NC-4.0 (yalnız deney) | R2 (retrieval) / R3 (`evaluation/**`) | — |
| C4 | DOING | `apps/api/.venv/bin/python scripts/measure_embedding_rss.py` (yeni dosya) → soğuk/sıcak RSS + peak `docs/test-report.md`'de | — | — | — |

## FAZ D' — Operasyon

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| D1' | DOING | `cd apps/api && TEST_DB_NAME=<oturum> .venv/bin/python -m pytest -q tests/test_token_quota_concurrency.py` (yeni dosya) — iki bağlantı, 2×3.000/5.000 → tam biri | — | R3 (`supabase/migrations/**`) | — |
| D2' | DOING | çapraz kullanıcı sızıntı testi yeşil; RLS bağlamı yalnız açık transaction içinde `SET LOCAL`; `pytest -q` rc=0 | — | R3 (`apps/api/app/core/db.py`) | — |
| D3' | DOING | `SIGTERM` tatbikatında iş kaybı yok; ölü-mektup kalanları raporlanır; `pytest -q` rc=0 | — | R3 (`apps/api/app/worker.py`) | — |
| D4' | DOING | `scripts/backup.sh` + `scripts/restore.sh` tatbikatı: satır sayıları ve dense arama sonucu aynı, `pg_restore --list` çıktısı `EXTENSION vector` içerir | — | — | — |
| D5' | BLOCKED | redaction testi: span'da prompt/öğrenci metni/JWT yok; `/internal/metrics` 200; alarm eşikleri belgede | ⛔ Logfire SDK | R3 (`apps/api/app/main.py`) | §4/1 |
| D6' | READY | `node scripts/docs_check.mjs` rc=0 — `ARCHITECTURE.md` ve `docs/security.md`'deki `/internal/drain` ve `dou_app` iddiaları koda uyar | — | — | — |
| S11 | READY | `python3 scripts/ai_sdlc_check.py --base-sha <taban> --head-sha <aday>` rc=0; kurtarılan kaynaklar hash listesiyle uzlaşır, eksik kanıt yeni koşuyla üretilir | — | R3 (`.ai/changes/**`) | — |

## FAZ E — Değerlendirme (`evaluation/**`)

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| E1 | BLOCKED | `promptfoo eval` exit≠100 (100 = kalite düşüşü); `PROMPTFOO_DISABLE_TELEMETRY=1`; `ai-quality.yml` adımı yeşil | ⛔ promptfoo (npm) | R3 | §4/1 |
| E2 | BLOCKED | `evaluation/evaluate.py --provider groq` damgalı sonuç üretir; kontrollü 429'da Cerebras'a geçer; yalnız `workflow_dispatch` | — | R3 | §4/3 |
| E3 | BLOCKED | ≥25 örnek holdout; iki etiketleyici, etiketler boş; Cohen's kappa raporlanır | — | R3 | §4/3 |
| E4 | READY | MCQ tutarlılık + çeldirici tekrarı + "hangi yanılgı"; açık uçlu rubrik QWK'si insan-insan uyumuna göre raporlanır | — | R3 | — |
| E5 | READY | `eval-fake` işi `.github/workflows/ai-quality.yml`'de yeşil; eşik `evaluation/calibration.md`'den okunur | — | R3 | — |
| E6 | READY | `EMBEDDING_PROVIDER=fastembed` ile eval korpusu HNSW'yi yeterli `maintenance_work_mem` ile kurar | — | R3 | — |

## FAZ F — Kimlik + private Storage

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| F1 | DOING | `cd apps/api && TEST_DB_NAME=<oturum> .venv/bin/python -m pytest -q` — sahte imza, süresi dolmuş, issuer/audience, `alg: none`, imzasız ve `alg != HS256` → 401 + `error.code` | — | R2 (`apps/api/app/core/config.py`) | — |
| F2 | BLOCKED | `kid` ile anahtar seçimi testi; JWKS erişilemezse kabul **yok** | — | R2 | §4/4 |
| F3 | BLOCKED | Entra tenant kısıtı uygulanır; rol enrollment tablosundan gelir; `dev:` yalnız `NEXT_PUBLIC_DEV_AUTH=true` iken | — | R2 | §4/2, §4/6 |
| F4 | READY | `migration_check` PASS (`supabase/migrations/0029_private_storage.sql`); imzalı URL kısa TTL; sunucu üyelik kontrolü ayrı testte | — | R3 (`supabase/migrations/**`) | §4/2 |
| F5 | READY | `supabase/tests/rls_storage.sql` (yeni dosya) + mutasyon betiği kırmızı yanar | — | — | — |
| F6 | BLOCKED | yerel Supabase yığınıyla E2E yeşil; gerçek proje yalnız anahtar geldiyse | — | — | §4/2 |

## FAZ G — Deploy

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| G1 | READY | GHCR imajı **digest** ile çekilir; `--network none` duman testi geçer; SBOM + Trivy + `actions/attest` tam SHA pinli | — | R3 (`apps/api/Dockerfile`) | §4/2 |
| G2 | DOING | `bash scripts/test_migrate.sh` (yeni dosya): temiz DB / N-1→N / no-op; `ON_ERROR_STOP`, advisory lock, dry-run | — | — | §4/2 |
| G3 | DOING | `.github/workflows/deploy.yml` (yeni dosya) yeşil: pull+up (digest) → migrate → `/health/ready` 200 → duman → önceki digest'e dönüş; `.release/verify_checks.py` iş envanteri değişmez | — | — | §4/2 |
| G4 | DOING | `.github/workflows/rollback.yml` (yeni dosya) yeşil; runbook'taki "15 dk geri alma" prova edilir | — | — | §4/2 |
| G5 | READY | `apps/api/.venv/bin/python scripts/workflow_policy_check.py` PASS; `keepalive.yml`'de `schedule` yok, `workflow_dispatch` var, kırmızı korunur | — | — | — |
| G6 | DOING | `node scripts/docs_check.mjs` rc=0 — `docs/deployment.md`: branch protection, required check adları, bütçe alarmı, Plan B/C | — | — | §4/8 |

## FAZ H — Frontend

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| H1 | READY | `cd apps/web && ./node_modules/.bin/playwright test --list` — LLM'e dokunan testler ayrı `project`; global `--workers=1` yok; karantina retry ≤1 + sahip + son tarih | — | — | — |
| H2 | READY | `toHaveScreenshot()` aynı Linux imajında yeşil | — | — | — |
| H3 | BLOCKED | axe kritik akışlarda ihlal 0 (375px + koyu tema); manuel klavye turu kaydı | ⛔ @axe-core/playwright | — | §4/1 |
| H4 | DOING | sınavda asistan ucuna doğrudan istek **gerçek sunucudan** 4xx döner (`route.fulfill` kanıt sayılmaz); kill-switch UI+API; sınav öncesi soru gövdesi ağda yok | — | R3 (`apps/web/components/course-assistant/**`) | — |
| H5 | BLOCKED | `eslint` rc=0 (flat config) | ⛔ ESLint 10 | — | §4/1 |
| H6 | READY | CSP report-only kurulu; dinamik rotalarda nonce; `cd apps/web && bunx tsc --noEmit` rc=0 | — | — | — |
| H7 | READY | ekran görüntüleri `supabase/seed_demo.sql` verisiyle üretilir | — | — | — |

## FAZ I — Belgeler, rapor, jüri (EN SON)

| id | durum | kabul komutu | B-kodu | risk | insan kararı? |
|---|---|---|---|---|---|
| I1 | DOING | `node scripts/docs_check.mjs` rc=0; §3/I1'de sayılan satırlardaki iddialar koda uyar veya kaldırılır | — | — | — |
| I3 | READY | `docs/test-report.md`: özet tablo + her satırda ölçüldü/koşulmadı ve tarih | — | — | — |
| I4 | READY | `specs/00[1-5]/tasks.md` kutucukları kanıtla eşleşir | — | — | — |
| I5 | READY | `python3 -m unittest scripts/test_ai_sdlc_check.py` — dossier önek-tekrarı kuralı testi yeşil | — | R3 (`scripts/ai_sdlc_check.py`) | — |
| I6 | READY | OpenAPI export güncel; `node scripts/check_links.mjs` (yeni dosya) rc=0 | — | — | — |
| I7 | READY | `node scripts/docs_check.mjs --duzelt` sonrası `node scripts/docs_check.mjs` rc=0 | — | — | — |
| I8 | BLOCKED | `docs/jury-demo.md` (yeni dosya): 10 dk senaryo, yalnız ölçülmüş sayılar; "KVKK uyumlu / production-ready / LTI hazır" ifadeleri geçmez | — | — | §4/5 |

> Runbook §3'ün FAZ I bölümünde **I2 yoktur** (I1, I3–I8 listelenmiştir); olmayan bir iş uydurulmadı.
