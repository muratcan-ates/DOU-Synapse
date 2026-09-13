# CODEX RUNBOOK v2 — DOU-Synapse production hattı: KALAN KUYRUK (13 Eylül 2026)

> Tek Codex oturumu kuyruktan iş çekerek kesintisiz çalışır. v1 (8 Eylül) ile Faz A, B, C1, D1 ve OPS dilimleri
> **tamamlandı** (PR #26, 14 commit, kanıt `specs/018-codex-production-line/verification.md`, dossier 025–036).
> v2 = 16 derin araştırma raporunun (Gemini + ChatGPT hakem turu) çapraz doğrulanmış kararları
> (`docs/team/codex/40-BIRLESIK-PLAN.md`) + kalan işler. Tamamlanan işi **yeniden açma**; kanıtı yeniden ölçmeden
> "bitti" de deme. Sıra: §0 kurallar → §1 durum → §2 döngü → §3 kuyruk. Yalnız §4'te dur, sonra sıradaki bağımsız işe geç.

---

## §0 — Kimlik, taban, pazarlık edilmeyen kurallar

**Depo:** `github.com/muratcan-ates/DOU-Synapse` (public). **Ürün ucu:** `017-completion-integration`.
**Çalışma dalın:** `018-codex-production-line` — açık; PR **#26** (draft, hedef 017) bu dalı izler. Kendi dalını açma.

```bash
git clone https://github.com/muratcan-ates/DOU-Synapse && cd DOU-Synapse
git checkout 018-codex-production-line && git pull --ff-only
cd apps/api && uv sync --extra dev --frozen && cd ../web && bun install && cd ../..
# PostgreSQL 16 + pgvector gerekir (docker compose up -d db). Yoksa DB kapıları not-run.
```
`.env` yok ve olmayacak. Testler `.env` istemez (`DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing`).

**Pazarlık edilmeyenler:**
1. **Ölçmediğini yazma.** "Geçti/çalışıyor/kanıtlandı" yalnız koşturduğun komutun çıktısıyla; koşamadıysan `not-run`.
   Sayı/SHA/dosya adı uydurma; beklenen çıktı sayısı yazma, kontrol koşulu yaz (`rc=0`; plan `Index Scan using chunks_embedding_idx` içerir).
2. **Kaynak yoksa cevap yok.** Kanıt eşiği altındaki sorgu LLM'e gitmeden ret döner; gevşetme.
3. **İki katmanlı yetki:** sunucu üyelik kontrolü **ve** aynı işlemde PostgreSQL RLS; mutasyon betikleri kırmızı yanabilmeli.
4. **Göçler:** düz SQL, dosya adı sırası; **0021–0023 boş kalır** (CI `--allow-gap`), 0024–0026 kullanıldı, **yeni göç 0027'den**.
   Geçmiş göç değişmez (dbmate yok). `python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023`.
5. **Yönetişim (`.ai/`)**: hassas yola dokunan commit aynı commit'te dossier + kanıt; append-only; numara = en büyük + 1 (bugün **037** dolu).
   CI yalnız **main'e push ve pull_request**'te koşar; PR'da doğrulayıcı tabanı **017 ucu** alır ve dossier yalnız HEAD'de
   tanıtıldığı commit'te + `base_sha` tabana eşitse sayılır. Protokol: her hassas commit kendi dossier'i (`base_sha`=ebeveyn, SELF);
   **her push'tan önce** `apps/api/.venv/bin/python scripts/refresh_aggregate_dossier.py --target origin/017-completion-integration`
   → `WROTE` ise `evaluation` gerçek dosyalara, kanıt `pass` (kanıt `result`, dossier `evidence[0].result`, `report_sha256`),
   `status: evidence-ready`, push'lanacak son commit'e ekle. **Bunu atlarsan PR'daki "Govern reviewed AI diff" kırmızı yanar** (8f2d324'te yandı).
6. **Dil:** kod İngilizce; yorum/UI/commit gövdesi Türkçe; conventional başlık; `Co-Authored-By` **asla**.
7. **Tasarım:** `DESIGN.md`; ikon kütüphanesi yok; iki temada AA.
8. **Bağımlılık** → §4/1 onay listesi; onaysız ekleme yok; gerekçe + alternatif yaz, sıradaki işe geç.
9. **Sır:** anahtar değeri hiçbir yere yazılmaz; yalnız GitHub Secrets/OIDC **adları**.
10. **Yayın onayı:** Codex'in 9 Eylül "S9 kod + sentetik kanıt arşivi paylaşım onayı" sorusu → Murat'ın cevabı sohbete gelene kadar
    o içerik sınıfında yeni push yok; diğer işler sürer.

**Kapılar — her commit'ten önce:**
```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME=dou_codex .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023
apps/api/.venv/bin/python scripts/workflow_policy_check.py
python3 scripts/ai_sdlc_check.py --base-sha "$(git merge-base origin/017-completion-integration HEAD)" --head-sha "$(git rev-parse HEAD)"   # commit sonrası, temiz ağaç
```

---

## §1 — Durum (13 Eylül 2026, ölçüldü)

**Codex'in ucu `8f2d324`:** ruff ✓ · mypy ✓ · pytest **1688 passed** · bun **573** ✓ · tsc ✓ · docs_check ✓ · workflow_policy PASS ·
Co-Authored-By yok · sır yok. PR #26 hosted: CI/Docs/Web/Image/Dependency/gold-set ✓; **Govern reviewed AI diff ✗** (toplayıcı
HEAD'de değildi → 037 eklendi); **CodeQL ✗** 3 yeni uyarı: `apps/web/e2e/audit-receipts.ts:130` TOCTOU (high),
`apps/api/app/modules/assessment/question_gen.py:611` log injection (medium), `specs/…/harness-v2/probe.py:463` bind all
interfaces (medium) — Claude düzeltiyor/düzeltti (bkz. commit geçmişi).

**Codex'in tamamladıkları (yeniden açma; kanıt `specs/018-…/verification.md`):** A1–A7 (release/mutasyon adımları CI'da, hassas kapılar
policy.json'da, workflow izin/`||true` kontrolü, `test.skip` kaldırıldı, zayıf testler, ölü yollar) · B1–B7 (konu bağlı çıktı, blueprint
akışı, kod rubriği + kaynaklı eksik ölçüt, sohbet silme UI + yarış kapatma (0024), politika geçmişi, kapalı authoring görünümü, sunucu
filtreleri) · C1 dense ANN yolu geri geldi (`dense.py:97` saf operatör, `:111` dış `file_hash` sırası; FTS sıra değişikliği kalite
düşürdü, geri çekildi) · D1 paylaşılan **istek** kotası Postgres'te (0025, `request_quota.py`) · D2/D3 yerel (worker lease 0026,
yedekten dönüş, log gizliliği) · OPS/D6 yönetim hazırlığı, portless poller · S1–S10 güvenlik dilimleri · I kılavuzlar (öğrenci/eğitmen/BİM).

**Codex'in açık bıraktıkları:** C1-FTS (yeniden yüklemede UUID sırasına bağımlılık) · C2 INCONCLUSIVE (bellek/recall) · S11 kalıcı silme
kuyruğu (aday, entegre değil) · D1/D2/D3 işletim (hedef ortam) · D4/D5 dış telemetri · E, F, G, H tamamen · I kalan (gerçek model raporu).

**Araştırma sonrası kararlar (özet; gerekçe 40-BIRLESIK-PLAN.md):** Azure Students `B2s_v2` 8 GiB VM (70–77 USD/ay → kredi ~6 hafta;
RSS ölç, sonra int8+Arm/Oracle) · DB Supabase Free (PITR yok → export + tatbikat) · Next standalone aynı VM · `scripts/migrate.sh` ·
`deploy.yml` ayrı + OIDC + digest · e5 korunur, reranker yalnız deney (jina v2 multilingual, CC-BY-NC) · Groq + Cerebras yedek + ZDR ·
gerçek eval yalnız `workflow_dispatch`, PR'da promptfoo yerel · HS256 Gün-1, JWKS 2 hafta · Entra tenant kısıtı, rol enrollment
tablosundan · actionlint+zizmor · diff-cover %85 · mutmut gecelik · AGENTS.md · learning_events · etiketli 429 fallback · LTI/FSRS ertelendi.

---

## §2 — Döngü (her iş)

1. Sıradaki READY işi al (`.ai/agent-queue.md` yoksa §3 sırası). 2. Dosyaların bugünkü hâlini oku (`git grep`). 3. Uygula; yalnız o işin
dosyaları; yeni dosyayı "yeni dosya:" işaretle. 4. Kapılar (§0). Kusur bulursan önce onu geçiren kapıyı güçlendir. 5. Hassas yol → dossier
(base=ebeveyn); push'tan önce toplayıcı. 6. Commit (Türkçe, neden) + push + PR #26'ya §5 satırı. 7. Sıradaki. Sorma; §4'te dur ve geç.
İş 2 saati aşarsa böl. Dış sebeple kırmızı kapı → `not-run` + sebep, iş bitmiş sayılmaz.

---

## §3 — Kalan kuyruk

### FAZ A' — Kapı hijyeni (kalan)

**A0. Ajan bağlamı.** `yeni dosya: AGENTS.md` (§0 kuralları + dosya haritası + kapılar, ≤120 satır), `yeni dosya: CLAUDE.md` = `@AGENTS.md` + 3 satır,
`yeni dosya: .ai/agent-queue.md` (§3 işleri: `id | READY/DOING/DONE/BLOCKED | kabul komutu | B-kodu | risk | insan kararı?`). `.cursorrules` yok. Kabul: docs_check rc=0.

**A3'. Workflow lint + pipefail.** `actionlint` + `zizmor` (⛔onay) `security.yml`'e adım, SHA-pinli; `psql` içeren her adımda `shell: bash`
(`-eo pipefail`) — actionlint bunu garanti etmez. Kabul: actionlint rc=0; bilerek bozuk `psql` adımı kırmızı (negatif kanıt).

**A4'. `test.skip/fixme` kapısı.** Skip'ler kaldırıldı; `ci.yml`'e sıfır bağımlılıklı kapı: `! git grep -nE 'test\.(skip|fixme)\(' -- apps/web/e2e`.
ESLint eklenmez (H5). Kabul: bilerek eklenen skip kapıyı kırar.

**A5'. Kanıt-betiği erişilebilirlik.** `scripts/ai_sdlc_check.py`'ye: `scripts/*check*.py`, `supabase/tests/*.sql`, `.release/test_*.py` en az bir
workflow'dan çağrılmalı; test `scripts/test_ai_sdlc_check.py`. Kabul: bir çağrıyı silince validator kırmızı. (R3 hassas → dossier.)

**A6'. AST test-kalite kapısı.** `yeni dosya: scripts/test_quality_check.py`: tek `status_code == 200` iddialı test, `pytest.raises` totolojisi,
çağrı içermeyen "sınar" testi → uyarı; sentetik fixture'larla testi; `ci.yml` adım. Kabul: bozuk fixture'da düşer.

**A8'. Değişen satır kapsaması.** `pytest-cov` + `diff-cover` (⛔onay; kurulu değil), `--fail-under=85 --compare-branch=origin/017-completion-integration`;
%100 yalnız RLS/yetki/göç dosyalarında ek hedef. Onay yoksa not-run.

**A9. `vulture`/`knip` (⛔onay)** ilk hafta uyarı modunda; FastAPI dekoratörleri ve Next rotaları beyaz listede.

### FAZ B' — Ürün: jüri Gün-1 çekirdeği (kalan)

**B3'. `learning_events` + mini eğitmen özeti.** `yeni göç: supabase/migrations/0027_learning_events.sql`
(`id, occurred_at, actor_pseudo_id, course_id, topic_id, session_id, event_type, object_type, object_id, outcome_json, evidence_chunk_ids,
latency_ms, model_id, metadata_json`) + RLS + mutasyon testi (`supabase/tests/`). Olaylar: `question_presented`, `answer_submitted`,
`hint_requested`, `citation_opened`, `unsupported_refusal`, `provider_rate_limited`. Eğitmen özeti: konu bazlı yanlış/ipucu/ret; ham sohbet yok.
"xAPI'ye eşlenebilir", xAPI değil. Kabul: olaylar yazılıyor; özet ucu + ekran; RLS kırmızı yanabiliyor; `migration_check` PASS.

**B4'. 429 → etiketli fallback + kapsam dışı ret demosu.** Sağlayıcı adaptörüne test bayrağıyla 429; bir `Retry-After` tekrarı; sonra
**"Önceden kaydedilmiş demo yanıtı"** etiketli fixture; sessiz model değişimi yok; kaynak kartları korunur. Kabul: E2E'de etiket görünür;
kapsam dışı soruda LLM çağrısı 0.

**B9. "Neden yanlış" kanıt kapısı doğrulaması.** B3 (kod rubriği) tamamlandı; açık uçlu/kod cevabında **çelişen kaynak parçası + sonraki ipucu**
gösterildiğini ve kanıt yoksa açıklama üretilmediğini E2E ile doğrula; eksikse tamamla. `code_trace`/`bug_hunt` deterministik oracle testi ≥1.

### FAZ C' — Retrieval (kalan)

**C1-FTS.** Yeniden yüklemede UUID sırasına bağımlılık: `fts.py` eşitlik bozmayı `documents.file_hash, chunk_index` ile (dense'teki gibi) dene;
kabul: hashing ve E5 holdout Recall@5/MRR **düşmez** (önceki denemede düştü → geri çekildi; aynı hata tekrarlanmaz), iki ingest aynı sıra.
**C2.** INCONCLUSIVE kaldı → karar: **göç eklenmez**; `docs/test-report.md`'ye "belirli kurulum koşulunda recall anomalisi gözlendi, nedensellik
kanıtlanmadı, regresyon testi korunur" notu; 0021 boş kalır. **C3. Reranker deneyi** (yalnız deney): `jinaai/jina-reranker-v2-base-multilingual`
(fastembed 0.8.0'da var; CC-BY-NC-4.0, 1,11 GB): 50 gold sorgu, top-24 sabit; NDCG@5/MRR@5/Recall@8/p95/peak RSS; kapı: NDCG@5 ≥ %5 göreli
**ve** RSS payı ≥ %20 **ve** p95 ≤ 500 ms; geçmezse varsayılan olmaz. `bge-reranker-v2-m3` yok; Docling/HyDE/contextual ertelendi.
**C4. e5 bellek ölçümü.** `yeni dosya: scripts/measure_embedding_rss.py` (soğuk/sıcak RSS, API+worker peak; qint8 562 MB smoke — AVX512-VNNI, ARM'da değil) → `docs/test-report.md`.

### FAZ D' — Operasyon (kalan)

**D1'. Token kotası aggregate penceresi.** 0025 istek kabulünü çözdü; sağlayıcı **token** bütçesi için sabit pencere `date_bin` + koşullu
`ON CONFLICT DO UPDATE … WHERE` tablosu (`yeni göç: 0028_ai_quota_windows.sql`) — yalnız `ai_token_reservations`'ın çok-süreçte yarış
verdiği ölçülürse; önce ölç (`yeni dosya: apps/api/tests/test_token_quota_concurrency.py`: iki bağlantı, 2×3.000/5.000 → tam biri).
`clock_timestamp()` pencere anahtarı olmaz. **D2'.** RLS bağlamı/GUC yalnız açık transaction içinde `SET LOCAL`; transaction pooler'da session
`SET`/LISTEN yok; asyncpg `statement_cache_size=0` (transaction mode ise); çapraz kullanıcı sızıntı testi. **D3'.** `SIGTERM` güvenli bırakma + ölü-mektup
kalanları; PgQueuer yok. **D4'.** `yeni dosya: scripts/backup.sh`/`restore.sh`; Supabase Free'de PITR yok → haftalık export; tatbikat: satır sayıları + dense arama
sonucu aynı, `pg_restore --list`'te `EXTENSION vector`. **D5'. Gözlem (⛔onay):** tek platform (Logfire EU aday); span'da prompt/öğrenci metni/JWT yok
(redaction testi); `/internal/metrics`; alarm eşikleri belgeye. **D6'.** `ARCHITECTURE.md:535`, `docs/security.md:278-280` (`/internal/drain` var);
`ARCHITECTURE.md:422-425,542` (Compose `dou_app`). **S11.** Kalıcı silme kuyruğu: kurtarılan kaynakları hash listesiyle uzlaştır, eksik kanıtı yeni koşuyla üret,
R3 dossier ile entegre et; eski sonucu yeni gibi yazma.

### FAZ E — Değerlendirme (`evaluation/**` R3)

**E1.** promptfoo (⛔onay npm) yerel Python provider: `yeni dosya: evaluation/injection/promptfooconfig.yaml` + `promptfoo_provider.py`;
Türkçe injection + Sokratik sızıntı kategorisi; `ai-quality.yml` adım; `PROMPTFOO_DISABLE_TELEMETRY=1`; exit 100 = kalite düşüşü. B3'ü kapatmaz.
**E2.** `evaluate.py --provider groq` gerçek koşucu; sonuç damgalı; önbellek gitignore; kota dolarsa kısmi; **yalnız `workflow_dispatch`**; Cerebras yedeği litellm
router'da, kontrollü 429 geçiş testi. Anahtar §4 → gelene kadar fake ile uçtan uca. **E3.** Holdout + kabul paketi: faithfulness, citation precision, ret,
abstention, sızıntı; ≥25 örnek; iki etiketleyici, etiketler boş; Cohen's kappa. **E4.** MCQ tutarlılık/çeldirici tekrar/"hangi yanılgı"; açık uçlu rubrik + ikinci
doğrulayıcı; QWK insan-insan uyumuna göre. **E5.** `eval-fake` işi `ai-quality.yml`'e (eşik `calibration.md`). **E6.** Eval korpusu HNSW'yi yeterli
`maintenance_work_mem` ile kurar; `EMBEDDING_PROVIDER=fastembed`.

### FAZ F — Kimlik + private Storage (`0022` boş kalır; yeni göç 0029)

Fail-closed kontroller `Settings`'te **var** (`config.py:348-354,365,381-396,412`); algoritma listesi kapalı. **F1.** JWT negatif testleri (sahte imza, süresi
dolmuş, issuer/audience, `alg: none`, imzasız → 401 + `error.code`; `alg != HS256` reddi). **F2.** HS256 kalır (§4/4); JWKS geçişi 2 hafta (`kid`, JWKS
erişilemezse kabul **yok**). **F3.** Supabase Auth giriş/şifre/refresh; **Entra tenant kısıtı**; rol enrollment tablosundan; `dev:` yalnız `NEXT_PUBLIC_DEV_AUTH=true`.
**F4.** Private Storage (`yeni göç: 0029_private_storage.sql`): imzalı URL kısa TTL, `storage.objects` RLS; `ingestion/storage.py:97` service_role RLS'i **atlar** → sunucu
üyelik asıl katman, testler **ayrı**. **F5.** `supabase/tests/rls_storage.sql` + mutasyon. **F6.** Yerel Supabase yığınıyla E2E; gerçek proje yalnız anahtar geldiyse.

### FAZ G — Deploy (karar: Azure Students VM)

**G1.** GHCR imaj + **digest**; çok aşamalı (bağımlılık → model katmanı → kod); `type=gha` cache; `--network none` duman korunur; SBOM + Trivy + `actions/attest`
tam SHA pin; ilk push süresini ölç. **G2.** `yeni dosya: scripts/migrate.sh` + `test_migrate.sh` (`ON_ERROR_STOP`, `app.schema_migrations` — §4/2, advisory lock,
dry-run, temiz DB / N-1→N / no-op). **G3.** `yeni dosya: .github/workflows/deploy.yml`: `workflow_run` yalnız trusted `main`; sır doğrulama; `azure/login` OIDC
(`AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID`); VM'de `docker compose pull`+`up` (digest) → migrate → `/health/ready` 200 → duman → önceki digest'e dönüş.
`B2s_v2`, Avrupa; Supabase Free; Next standalone aynı VM. Sır **adları**: `DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, GROQ_API_KEY`.
`verify_checks.py` iş envanteri değişmez. **G4.** `rollback.yml` + runbook "15 dk geri alma". **G5.** `keepalive.yml`: `schedule` kaldır, dispatch kalsın, kırmızı korunur.
**G6.** `docs/deployment.md`: branch protection, required check adları, Azure budget alert (~6 hafta), Plan B Oracle A1 / Plan C Hetzner CX33 (ARM için `linux/arm64` kanıtı).

### FAZ H — Frontend

**H1.** LLM'e dokunan Playwright testleri ayrı `project` + worker fixture; global `--workers=1` yok; flaky karantina (retry ≤1, sahip, son tarih). **H2.** `toHaveScreenshot()`
aynı Linux imajında. **H3.** `@axe-core/playwright` (⛔onay) kritik akışlar, 375px + koyu; manuel klavye turu. **H4.** Sınavda asistan ucuna doğrudan istek → gerçek
sunucudan 4xx (`route.fulfill` kanıt değil); kill-switch UI+API; sınav öncesi soru gövdesi ağda yok. **H5.** ESLint 10 flat config (⛔onay, hafta 1). **H6.** CSP report-only →
dinamik rotalarda nonce. **H7.** Ekran görüntüleri seed verisiyle.

### FAZ I — Belgeler, rapor, jüri (EN SON)

**I1.** Yanlış iddialar: `ARCHITECTURE.md:34,533-535` · `docs/security.md:288-296,309-316` · `:22,24,53,110,118,208,262,275,277,305` · `:169-175` · `docs/runbook.md:143-147,155,191,236-241` ·
`PLAN.md:175` · `docs/completion-program.md` · `README.md:508-527` göç tablosu (0024–0026+) · `specs/001-…/quickstart.md:99`. **I3.** Başarı testi raporu: özet tablo,
ölçüldü/koşulmadı + tarih. **I4.** `specs/00[1-5]/tasks.md` kutucukları kanıtla. **I5.** İki `010-*` dossier → `ai_sdlc_check.py` önek-tekrarı kuralı + test. **I6.** OpenAPI export +
`scripts/check_links.mjs`. **I7.** `docs_check --duzelt`. **I8.** `yeni dosya: docs/jury-demo.md`: 10 dk senaryo (kanıtlı cevap → kanıt yok → sus; 429 → etiketli fallback;
eğitmen özeti); yalnız ölçülmüş sayılar; "KVKK uyumlu / production-ready / LTI hazır" **denmez**; YÖK 7 May 2024; TÜBİTAK 2209 2026 çağrısı ilan edilmedi, BiGG 1812 1,35M/%3;
AI Act: sınav provası nota girmez + Art. 6(3) + yüksek-risk yükümlülükleri 2 Ara 2027.

---

## §4 — Murat'a sorulacaklar (dur, yaz, sıradakine geç)

| # | Ne | İş | Varsayılan |
|---|---|---|---|
| 1 | Bağımlılık onayı: `actionlint`, `zizmor`, `pytest-cov`+`diff-cover`, `promptfoo`, `mutmut`, `vulture`, `knip`, `@axe-core/playwright`, ESLint 10, Logfire SDK | A3' A8' A9 E1 H3 H5 D5' | İlk beşi onayla |
| 2 | Azure for Students + `B2s_v2` + Entra app kaydı (OIDC); `app.schema_migrations` runner açsın; Supabase projesi → GitHub Secrets | G F | Evet; değerler sohbete yazılmaz |
| 3 | Groq ZDR aç; Cerebras hesabı; Groq anahtarı dispatch sırrı | E2 E3 B4' | Evet |
| 4 | JWT: HS256 kalsın, JWKS 2 hafta | F2 | Evet |
| 5 | Sınav provası sonuçları nota/geçme-kalmaya **girmez** (AI Act 6(3)) | I8 | Evet |
| 6 | DOUZEM/BİM: LTI 1.3 dış araç; Entra tenant ID | F3 (2 hafta) | LTI vaat edilmez |
| 7 | **S9/S10 kod + sentetik kanıt arşivi paylaşım onayı** (Codex'in 9 Eylül sorusu) | §0/10 | Onay bekleniyor |
| 8 | Kredi bitince: Oracle A1 mi Hetzner CX33 mü | G6 | RSS ölçümünden sonra |

Format: **ne · neden · alternatif · beklerken ne yapıyorum.**

## §5 — Rapor biçimi (her push'ta PR #26 açıklamasına)
```
[Faz X / İş N] <başlık>
Yapılan: <2-3 cümle, neden dahil>
Kapılar: pytest rc · bun rc · tsc rc · ruff rc · mypy rc · docs_check rc · migration_check rc · workflow_policy · ai_sdlc rc
Not-run: <ne, neden> · Dossier: <NNN> · Toplayıcı: OK/WROTE · Engel: <§4 maddesi>
```
