# ŞERİT L5 — Kimlik ve private Storage
**Dal:** `018-l5-auth` · **Dossier aralığı:** 080–089 · **Göç:** `supabase/migrations/0029_private_storage.sql` · **PR başlığı:** `[L5] …`
**Yüzeyin:** `apps/api/app/core/security.py`, `apps/api/app/core/config.py` (yalnız yeni alan), `apps/api/app/modules/ingestion/storage.py`, `apps/api/app/api/documents.py` (imzalı URL), `apps/web/lib/auth*`, `apps/web/app/(auth)/**` ya da giriş sayfası, `supabase/migrations/0029_*`, `supabase/tests/rls_storage.sql`, `supabase/tests/rls_storage_mutation_check.sh`, `apps/api/tests/test_auth*`, `test_storage*`.
**Dokunma:** retrieval, assessment, workflow'lar, `scripts/*check*`.
**Karar verildi:** HS256 Gün-1'de kalır (JWKS geçişi ayrı iş, henüz değil); Supabase Auth + **Entra tenant kısıtı**; rol e-posta alan adından **değil**, enrollment tablosundan; `service_role` Storage RLS'i **atlar** → sunucu üyelik kontrolü asıl katman.
**Sırlar yok** (Supabase projesi açılınca gelecek) → F3/F6'nın canlı kısmı `not-run`; yerel/sentetik kısımları yap.

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

**F1. JWT negatif testleri.** `apps/api/tests/test_auth_negative.py` (varsa genişlet): sahte imza, süresi dolmuş, yanlış issuer, yanlış audience, `alg: none`, imzasız, `alg != HS256` → 401 + `error.code`; sessiz fallback yok; `jwt_algorithms` listesinin kapalı olduğu test. Fail-closed `Settings` doğrulayıcıları (`config.py:348-354, 365, 381-396, 412`) için `create_app()`'in fırlattığı test (varsa doğrula).

**F3. Web oturumu (dev yolu korunarak).** Supabase Auth ile giriş / şifre sıfırlama / e-posta doğrulama / refresh akışının web tarafı; 401'de tek yerden çıkış; `dev:` girişi yalnız `NEXT_PUBLIC_DEV_AUTH=true` iken görünür (silme). Entra sağlayıcı düğmesi tenant kısıtlı (`NEXT_PUBLIC_ENTRA_TENANT_ID` adı; değer yok). Rol: JWT claim'i yalnız `authenticated`; pedagojik rol sunucuda enrollment tablosundan. Kabul: `bun test lib/`; tsc; E2E yerel (`dev:`) kırılmadı; gerçek Supabase `not-run`.

**F4. Private Storage.** `yeni göç: 0029_private_storage.sql`: `storage.objects` için RLS politikaları (ders üyeliğine göre okuma; yazma yalnız eğitmen; silme sahibi/eğitmen) — yerel Postgres'te `storage` şeması yoksa göç `IF EXISTS`/koşullu ve testte şema sentetik kurulur (belgele). API: dosya indirme **imzalı URL** (kısa TTL, `documents.py`), doğrudan public URL yok; `STORAGE_BACKEND=supabase` yolu `storage.py:97` service_role ile kalır **ama** üyelik kontrolü önce.

**F5. `supabase/tests/rls_storage.sql` + mutasyon betiği.** Gerçek kullanıcı jetonu simülasyonuyla (JWT claim set) listeleme/indirme/silme reddi; politika bilerek bozulunca kırmızı. `psql -X -v ON_ERROR_STOP=1`. CI adımı L1 ekler → PR notu.

**F6.** Yerel Supabase yığını (`supabase start`) ile E2E — Docker varsa; gerçek proje yalnız anahtar geldiyse, yoksa `not-run`.

**F2 (yalnız hazırlık, uygulama yok):** JWKS geçiş planı `docs/security.md` yeni bölüm: `kid` çözümü, JWKS erişilemezse **kabul yok**, geçiş penceresi, eski anahtar iptali.

**Başla:** F1 → F3 → F4 → F5 → F2(belge) → F6.
