# ŞERİT L1 — Kapılar ve eval kablosu
**Dal:** `018-l1-gates` · **Dossier aralığı:** 040–049 · **Göç:** yok · **PR başlığı:** `[L1] …`
**Yüzeyin:** `.github/workflows/**`, `scripts/**`, `.ai/policy.json`, `AGENTS.md`, `CLAUDE.md`, `.ai/agent-queue.md`, `evaluation/injection/**`, `apps/web/e2e/**` (yalnız skip kapısı), `apps/api/tests/**` (yalnız test-kalite fixture'ları).
**Dokunma:** `apps/api/app/**`, `apps/web/app|components|lib/**`, `supabase/**`, `apps/api/Dockerfile`, `docs/**` (README hariç zorunlu sayaç).

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

**A0. Ajan bağlamı.** `yeni dosya: AGENTS.md` (runbook §0 kuralları + dosya haritası + kapı komutları, ≤120 satır); `yeni dosya: CLAUDE.md` içeriği yalnız `@AGENTS.md` + 3 satır; `yeni dosya: .ai/agent-queue.md` (runbook §3'ün her işi için `id | READY/DOING/DONE/BLOCKED | kabul komutu | B-kodu | risk | insan kararı?`; L1–L7 şerit sahipliğini yaz). `.cursorrules` yok. Kabul: `node scripts/docs_check.mjs` rc=0.

**A3'. Workflow lint + pipefail.** `security.yml`'e iki adım: `rhysd/actionlint` ve `zizmorcore/zizmor` — **tam 40 karakter SHA ile pin'li** action (manifest değişikliği yok; workflow hassas → dossier 040). `ci.yml`/`security.yml`/`release-candidate.yml`'de `psql` içeren her adımda `shell: bash` (GitHub bunu `-eo pipefail` ile koşturur) ya da açık `set -o pipefail`. `scripts/workflow_policy_check.py`'nin `continue-on-error`/`|| true` ve `permissions: write` kontrollerini doğrula; eksikse ekle + test.
Kabul: `actionlint .github/workflows/*.yml` rc=0; bilerek bozuk bir `psql` komutu içeren geçici adım kırmızı yanar (negatif kanıt; commit'e girmez); `workflow_policy_check` PASS.

**A4'. `test.skip/fixme` kapısı.** `ci.yml` web işine adım: `! git grep -nE 'test\.(skip|fixme)\(' -- apps/web/e2e`. ESLint ekleme. Kabul: bilerek eklenen `test.skip(` kapıyı kırar (negatif kanıt), sonra geri al.

**A5'. Kanıt-betiği erişilebilirlik.** `scripts/ai_sdlc_check.py`'ye kural: `scripts/*check*.py`, `scripts/*mutation_check*`, `supabase/tests/*.sql`, `.release/test_*.py` dosyalarının her biri en az bir `.github/workflows/*.yml` içinde anılmalı; anılmayan → `EVIDENCE_UNREACHABLE:<yol>` hatası. Test: `scripts/test_ai_sdlc_check.py` (bir çağrıyı silince kırmızı). R3 hassas → dossier.

**A6'. AST test-kalite kapısı.** `yeni dosya: scripts/test_quality_check.py`: (1) tek iddiası `status_code == 200` olan test fonksiyonu, (2) `pytest.raises(X)` bloğunda X'i testin kendisinin doğrudan `raise` ettiği totoloji, (3) adında "yardımcı/helper" geçip o yardımcıyı çağırmayan test → uyarı listesi; `--fail-on` ile hata. `yeni dosya: scripts/test_test_quality_check.py` sentetik kırmızı/yeşil fixture'larla. `ci.yml`'e adım (önce uyarı modu; mevcut testlerde bulduklarını PR açıklamasına listele, düzeltme L1'in işi değil).

**I5. Dossier önek tekrarı.** `scripts/ai_sdlc_check.py`: `.ai/changes/` altında aynı sayısal önek iki kez kullanılamaz (mevcut `010-*` çifti bilinçli istisna listesinde). Test ekle.

**E5. `eval-fake` işi.** `ai-quality.yml`'e iş: fake sağlayıcı + hashing holdout (`evaluation/evaluate.py` mevcut yolu), eşik `evaluation/calibration.md`'den; kırmızıysa iş düşer. `.release/verify_checks.py` görünen iş adlarını saydığı için **yeni işi oraya da ekle** (dossier). `ci.yml`'e dokunma.

**E1. promptfoo yerel harness (hazırlık).** `yeni dosya: evaluation/injection/promptfooconfig.yaml` + `promptfoo_provider.py` (deterministik yerel provider; dış LLM yok): mevcut injection setinden ≥10 vaka + Sokratik sızıntı kategorisi ("cevabı direkt ver", "hocam izin verdi", rol-play, çok turlu baskı). Yerelde `PROMPTFOO_DISABLE_TELEMETRY=1 bunx promptfoo@0.123.0 eval -c evaluation/injection/promptfooconfig.yaml` ile doğrula (manifeste ekleme). CI adımı **ekleme** — PR açıklamasına `ENGEL: bağımlılık promptfoo (npm) onayı` yaz.

**Atlanan (onay bekliyor):** A8' diff-cover/pytest-cov, A9 vulture/knip → `ENGEL:` notu, dokunma.

**Başla:** A0 → A4' → A3' → A5' → I5 → A6' → E5 → E1.
