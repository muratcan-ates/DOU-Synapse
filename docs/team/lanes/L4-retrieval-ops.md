# ŞERİT L4 — Retrieval ve operasyon (mevcut Codex sohbetinin devamı)
**Dal:** `018-l4-retrieval-ops` · **Dossier aralığı:** 070–079 · **Göç:** `supabase/migrations/0028_ai_quota_windows.sql` (yalnız ölçüm gerektiriyorsa) · **PR başlığı:** `[L4] …`
**Yüzeyin:** `apps/api/app/modules/retrieval/**`, `apps/api/app/core/rate_limit.py`, `apps/api/app/core/request_quota.py`, `apps/api/app/worker.py`, `apps/api/app/modules/ingestion/**` (yalnız worker dayanıklılığı), `apps/api/tests/test_retrieval*`, `apps/api/tests/test_token_quota_concurrency.py`, `scripts/measure_embedding_rss.py`, `docs/test-report.md` (yalnız yeni bölümler), `ARCHITECTURE.md:422-425,535,542`, `docs/security.md:278-280`, `evaluation/results/**` (deney sonuçları; R3 dossier).
**Dokunma:** `apps/web/**`, workflow'lar, `scripts/*check*`, `Dockerfile`, storage/auth.

## ORTAK KURALLAR (her şerit için aynı — değiştirme)

**Depo:** `github.com/muratcan-ates/DOU-Synapse` (public). Entegrasyon dalı `018-codex-production-line` (PR #26 → 017). Sen kendi dalında çalışırsın.

```bash
git clone https://github.com/muratcan-ates/DOU-Synapse && cd DOU-Synapse
git fetch origin && git checkout 018-codex-production-line && git pull --ff-only
git checkout -b <DAL>            # şerit dosyasındaki dal adı; varsa: git checkout <DAL> && git pull --ff-only
cd apps/api && uv sync --extra dev --frozen && cd ../web && bun install && cd ../..
# PostgreSQL 16 + pgvector gerekir (docker compose up -d db). Yoksa DB isteyen kapılara "not-run" yaz.
```
Önce oku: `docs/team/codex/CODEX-RUNBOOK.md` (v2) §0 ve §2; kararların gerekçesi `docs/team/codex/40-BIRLESIK-PLAN.md`.

**Pazarlık edilmeyenler**
1. Ölçmediğini yazma. "Geçti/çalışıyor" yalnız koşturduğun komut çıktısıyla; koşamadıysan `not-run`. Sayı, SHA, dosya adı uydurma; var olmayan dosyayı `yeni dosya:` diye işaretle. Beklenen çıktı sayısı yazma, kontrol koşulu yaz.
2. Kaynak yoksa cevap yok (kanıt eşiği gevşetilmez). 3. İki katmanlı yetki: sunucu üyelik + PostgreSQL RLS. 4. Geçmiş göç dosyası değişmez; 0021–0023 boş kalır; yeni göç numaran şerit dosyasında.
5. `Co-Authored-By` asla. Kod/dosya adı İngilizce; yorum, UI metni, commit gövdesi Türkçe; conventional başlık; gövdede **neden**.
6. `.env` oluşturma, sır yazma (anahtar değeri hiçbir yere). 7. `DESIGN.md` tek tasarım otoritesi; ikon kütüphanesi yok; iki temada AA.
8. **Bağımlılık:** `pyproject.toml`, `uv.lock`, `package.json`, `bun.lock` **değiştirme** (lider onayı bekleniyor). Gerekiyorsa PR açıklamasına `ENGEL: bağımlılık <ad>` yaz, işi atla. SHA-pinli GitHub Action eklemek serbest (dossier ister).
9. **Başka şeridin yüzeyine dokunma** (şerit dosyasındaki "Dokunma" listesi). Ortak dosyaya (README, ci.yml) zorunlu dokunuşu en küçük tut ve PR açıklamasında belirt.
10. Sorma; §4 türü karar gerekirse `ENGEL:` yaz ve sıradaki işe geç.

**Kapılar — her commit'ten önce, hepsi yeşil**
```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME=dou_<serit> .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023
apps/api/.venv/bin/python scripts/workflow_policy_check.py
# commit SONRASI, temiz ağaçta (taban = ebeveyn commit; yalnız kendi dossier'in sınanır):
python3 scripts/ai_sdlc_check.py --base-sha "$(git rev-parse HEAD~1)" --head-sha "$(git rev-parse HEAD)"
```
Yeni test eklediysen belge sayaçları için `node scripts/docs_check.mjs --duzelt` (web bağımlılıkları + `bunx playwright install chromium` kuruluyken).

**Yönetişim (`.ai/`)** — `.ai/policy.json`'daki hassas yola (workflow'lar, `scripts/*check*`, `apps/api/app/modules/{assessment,retrieval,generation,guardrails,ingestion,agent,policy,mastery}/**`, `apps/api/app/api/{chat,policy,blueprints,exams,privacy,questions}.py`, `config.py`, `rate_limit.py`, `evaluation/**`, `apps/web/app/courses/**/chat/**`, `components/course-assistant/**` …) dokunan **her commit aynı commit'te** dossier + kanıt taşır:
`.ai/changes/<NNN>-<konu>-r1.json` + `.ai/evidence/<NNN>-<konu>-r1.json`; şablon `.ai/changes/example.json` ve `.ai/changes/037-codeql-hardening-r1.json`.
`NNN` = şerit dosyandaki **aralıktan** sırayla (başkasıyla çakışmasın diye). `base_sha` = üstüne inşa ettiğin commit'in tam SHA'sı, `candidate_sha: "SELF"`,
`artifacts[].sha256` = dosyanın gerçek özeti, `evidence[0].report_sha256` = kanıt dosyasının gerçek özeti, `status: "evidence-ready"`, kanıt `result: "pass"` yalnız koştuğun komutlarla.
`evaluation.calibration_ref/holdout_ref/human_anchor_ref` **gerçek dosya** olmalı. Kayıtlar append-only: var olanı düzenleme.
**`scripts/refresh_aggregate_dossier.py` KOŞTURMA** — toplayıcı kaydı entegrasyonda Claude yazar. PR'ında "Govern reviewed AI diff" bu yüzden kırmızı olabilir; **normaldir**.

**PR ve rapor** — Her iş bittiğinde commit + push; ilk push'ta `018-codex-production-line` hedefli **draft PR**, başlık `[<ŞERİT>] <iş>`. PR açıklamasına her push'ta:
```
[<ŞERİT> / İş N] <başlık>
Yapılan: <2-3 cümle, neden dahil>
Kapılar: pytest rc · bun rc · tsc rc · ruff rc · mypy rc · docs_check rc · migration_check rc · workflow_policy · ai_sdlc(ebeveyn) rc
Not-run: <ne, neden> · Dossier: <NNN> · ENGEL: <varsa>
```
İş 2 saati aşarsa böl. Dış sebeple (DB yok, kota) kırmızı kapı → `not-run` + sebep; işi bitmiş sayma.

## İŞLER (sırayla)

**C4. e5 bellek ölçümü (barındırma kararının girdisi).** `yeni dosya: scripts/measure_embedding_rss.py`: soğuk/sıcak RSS, ingest sırasında peak, API+worker birlikte peak (RSS, `psutil` yoksa `/proc` ya da `ps`); upstream qint8 (562 MB, AVX512-VNNI) yüklenebilirlik smoke (bu makinede). Sonuç `docs/test-report.md` yeni bölüm (tarih, komut, sayılar). Kabul: betik rc=0; bölüm ölçümle.

**C1-FTS.** Yeniden yüklemede UUID sırasına bağımlılık: `fts.py` eşitlik bozmayı `documents.file_hash, chunk_index` ile dene (dense'teki desen). **Kabul:** hashing ve E5 holdout Recall@5/MRR **düşmez** (önceki deneme düştü ve geri çekildi — aynı hata tekrarlanmaz); iki ingest aynı sıra; yapısal test `str(_SQL)`. Düşerse değişikliği alma, sonucu raporla.

**C2.** INCONCLUSIVE → karar: **göç eklenmez**; `docs/test-report.md`'ye "belirli kurulum koşulunda recall anomalisi gözlendi, nedensellik kanıtlanmadı, regresyon testi korunur" notu; 0021 boş kalır.

**C3. Reranker deneyi (yalnız deney, varsayılan yapılmaz).** `jinaai/jina-reranker-v2-base-multilingual` (fastembed 0.8.0'da var; **CC-BY-NC-4.0** — kabul paketine lisans notu; 1,11 GB). 50 gold sorgu, top-24 aday sabit; rerank'siz vs rerank NDCG@5, MRR@5, Recall@8, p50/p95, peak RSS. Kapı: NDCG@5 ≥ %5 göreli **ve** RSS'de ≥ %20 pay **ve** p95 ≤ 500 ms. Sonuç `evaluation/results/<ts>-rerank-experiment.json` + rapor bölümü. `bge-reranker-v2-m3` fastembed'de **yok**; Docling/HyDE/contextual **ertelendi**.

**D1'. Token kotası (önce ölç).** `yeni dosya: apps/api/tests/test_token_quota_concurrency.py`: iki ayrı bağlantı/işlem, aynı anda 2×3.000 token, limit 5.000 → **tam biri** geçer; toplam 3.000; iptal sonrası tekrar alınır. Mevcut `ai_token_reservations` bunu geçiyorsa göç **yok**. Geçmiyorsa `yeni göç: 0028_ai_quota_windows.sql`: sabit pencere `date_bin` + `INSERT … ON CONFLICT DO UPDATE SET reserved += … WHERE reserved+consumed+istek <= limit RETURNING` (kabulde 1 satır, redde 0); `clock_timestamp()` pencere anahtarı **olmaz**; `ai_token_reservations` audit/idempotency için kalır.

**D2'.** RLS bağlamı ve HNSW GUC'ları yalnız **açık transaction içinde** `SET LOCAL`; transaction pooler'da session `SET`/LISTEN yok; asyncpg `statement_cache_size=0` (transaction mode ise); çapraz kullanıcı sızıntı testi.

**D3'.** Worker: `SIGTERM` güvenli bırakma + ölü-mektup kalanları (0026 lease üstüne); PgQueuer **yok**. Kabul: bozuk belge → N deneme → `failed` + ölü-mektup; SIGTERM testi.

**D6'.** `ARCHITECTURE.md:535`, `docs/security.md:278-280` (`/internal/drain` var, "uygulanmadı" yazıyor); `ARCHITECTURE.md:422-425,542` (Compose `dou_app` kullanıyor, "superuser" yazıyor).

**S11.** Kalıcı silme kuyruğu: 9 Eylül'de kurtarılan kaynakları kayıtlı hash listesiyle uzlaştır; eksik ham kanıtı **yeni koşuyla** üret; tam API + gerçek CLI kabulü; R3 dossier ile entegre et. Eski sonucu yeni gibi yazma.

**Başla:** C4 → C1-FTS → C2 → D1' → D2' → D3' → C3 → D6' → S11.
