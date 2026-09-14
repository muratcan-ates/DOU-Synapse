# ŞERİT L3 — Deploy ve CI/CD
**Dal:** `018-l3-deploy` · **Dossier aralığı:** 060–069 · **Göç:** yok · **PR başlığı:** `[L3] …`
**Yüzeyin:** `apps/api/Dockerfile`, `docker-compose.yml`, `scripts/migrate.sh`, `scripts/test_migrate.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `.github/workflows/deploy.yml`, `.github/workflows/rollback.yml`, `.github/workflows/keepalive.yml`, `.github/workflows/release-candidate.yml` (imaj/SBOM adımları), `.release/**`, `docs/deployment.md`, `docs/runbook.md`.
**Dokunma:** `ci.yml`, `security.yml`, `ai-quality.yml`, uygulama kodu, `supabase/migrations/**` (yalnız runner okur).
**Karar verildi:** Azure for Students `Standard_B2s_v2` (2 vCPU/8 GiB, Ubuntu 24.04) tek VM, Docker Compose; DB Supabase Free; web Next `output: "standalone"` aynı VM; kimlik OIDC (`AZURE_CLIENT_ID/AZURE_TENANT_ID/AZURE_SUBSCRIPTION_ID`), statik bulut parolası yok. Sırlar henüz **yok** → workflow'lar sır adlarıyla yazılır, gerçek dağıtım `not-run`.

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

**G2. Göç runner.** `yeni dosya: scripts/migrate.sh` (+ `scripts/test_migrate.sh`): `supabase/migrations/NNNN_*.sql` sıralı; `psql -X -v ON_ERROR_STOP=1`; `app.schema_migrations(version, applied_at, sha256)` (`CREATE TABLE IF NOT EXISTS` runner açar); `pg_advisory_lock`; `--dry-run` yalnız bekleyenleri listeler; başarı kaydı yalnız rc=0 sonra; her dosyayı körce `-1` içine **alma** (transaction dışı SQL olabilir); geçmiş dosya **değişmez**; uygulanmış dosyanın sha256'sı değişmişse hata. Test: temiz DB tüm göçler; N-1→N; ikinci koşum no-op; kuru koşu; bozuk SQL'de rc≠0. `ci.yml`'e adım L1 ekler → PR notu.

**G1. İmaj.** `apps/api/Dockerfile` çok aşamalı: bağımlılıklar → `scripts/bake_embedding_model.py` model katmanı → uygulama kodu (**kod modelin arkasında**); `type=gha` cache; `--network none` duman testi korunur. `release-candidate.yml`'e: GHCR push `ghcr.io/muratcan-ates/dou-synapse-api:<sha>` + **digest çıktısı**, SBOM (CycloneDX) + Trivy imaj taraması + `actions/attest` — hepsi tam 40 karakter SHA pin. İlk push süresini ölç, uydurma.

**G3. `yeni dosya: .github/workflows/deploy.yml`.** `workflow_run` (ci başarılı, yalnız `main` — PR head checkout **yok**) + `workflow_dispatch(digest)`; environment `staging`; sır doğrulama adımı (`DEV_AUTH_ENABLED=false`, `EMBEDDING_PROVIDER=fastembed`, `STORAGE_BACKEND=supabase` değilse düş); `azure/login` OIDC (SHA pin); VM'e SSH (`STAGING_SSH_KEY`, `azureuser@<ip>`) → `docker compose pull` (digest) + `up -d` → `scripts/migrate.sh` (direct DB URL) → `/health/ready` 200 bekle (**`/openapi.json` değil**) → duman (giriş + ders listesi) → başarısızlıkta önceki digest. Sırlar yalnız **ad**: `DATABASE_URL, WORKER_DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, GROQ_API_KEY, STAGING_SSH_KEY, AZURE_*`. `.release/verify_checks.py` iş envanteri değişmez. Kabul: `actionlint` rc=0; `workflow_policy_check` PASS; canlı koşu `not-run` (sır yok).

**G4. `yeni dosya: .github/workflows/rollback.yml`** (`workflow_dispatch`, digest girdisi) + `docs/runbook.md` "15 dk geri alma" + göç geri alma politikası (expand–contract).

**G5. `keepalive.yml`:** `schedule` kaldır, `workflow_dispatch` kalsın; eksik sırda **kırmızı** davranışı korunur (`continue-on-error` yok).

**D4'. Yedek/geri yükleme.** `yeni dosya: scripts/backup.sh` (`pg_dump -Fc`), `scripts/restore.sh`; tatbikat testi: dolu DB → yedek → boş DB → satır sayıları **ve** bir dense arama sonucu aynı; `pg_restore --list`'te `EXTENSION vector` görünür. Supabase Free'de PITR yok → haftalık export notu `docs/runbook.md`'ye.

**G6. `docs/deployment.md`:** branch protection ve required check adları (`API — lint, tip, test`, `Web — lint, tip`, `Belgeler — canlı sayı kapısı`, `API imajı — build + ağsız embedding kanıtı`, `Uçtan uca — gerçek API + tarayıcı`, `Govern reviewed AI diff`, `Verify gold-set integrity`, `Workflow dependency policy`, `CodeQL (python)`, `CodeQL (javascript-typescript)`), environment reviewers, Azure budget alert (kredi ~6 hafta), Plan B Oracle A1 / Plan C Hetzner CX33 (ARM için `linux/arm64` imaj + fastembed kanıtı şart), VM deallocate notu.

**Başla:** G2 → G5 → G1 → G3 → G4 → D4' → G6.
