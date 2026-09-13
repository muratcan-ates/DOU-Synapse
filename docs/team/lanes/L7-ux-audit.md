# ŞERİT L7 — UX denetimi ve küçük düzeltmeler (tasarım turu)
**Dal:** `018-l7-ux` · **Dossier aralığı:** 100–109 · **Göç:** yok · **PR başlığı:** `[L7] …`
**Yüzeyin:** `apps/web/app/**`, `apps/web/components/**`, `apps/web/lib/**` (kopya/durum/odak), `docs/ux-audit-2026-09.md`.
**Dokunma:** `apps/api/**`, `apps/web/e2e/**` (L6), workflow'lar, `DESIGN.md` (salt okunur; değiştirmek istersen PR'da öner).
**Sınırlar:** Büyük yeniden tasarım **yok** (3 gün var). İkon kütüphanesi yok, elle SVG yok (marka işareti hariç), yeni bağımlılık yok, renk tek başına bilgi taşımaz, iki temada AA (`node scripts/contrast.mjs` kapısı). Sohbet/asistan yüzeyleri (`apps/web/app/courses/**/chat/**`, `components/course-assistant/**`) hassas → dossier.

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

**U1. Denetim (önce yaz, sonra düzelt).** Uygulamayı yerelde seed verisiyle kaldır (`DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing`, `docker compose up -d db`, `bun dev`), üç rolle (öğrenci / eğitmen / Bilgi İşlem) her sayfayı 1440px açık, 375px koyu ve yalnız klavye ile gez. `yeni dosya: docs/ux-audit-2026-09.md`: tablo `sayfa | rol | bulgu | önem P0/P1/P2 | tekrar adımı | DESIGN.md maddesi | öneri`. Kapsam: boş/yükleniyor/hata durumları, kopya (Türkçe, tutarlı terim: "ders", "konu", "blueprint", "kaynak"), odak halkası ve sırası, dialog `aria-modal`/odak dönüşü, canlı bölge, kontrast, mobil taşma, "mock gibi duran" yerler, ölü düğmeler (bayrak kapalıyken), yanıltıcı başarı mesajları. Ekran görüntüsü yolunu yaz (seed veri).

**U2. P0/P1 düzeltmeleri (küçük, ölçülebilir).** Her düzeltme: önce/sonra ekran görüntüsü (seed), `bun test lib/` + tsc + `node scripts/contrast.mjs` yeşil; DESIGN.md dışına çıkma; kopya değişiklikleri Türkçe ve tutarlı. Öncelik: sınav çalışma alanı, "neden yanlış" paneli, kaynak kartları, ret/abstain durumu, eğitmen ders ayarları, giriş/çıkış. P2'ler yalnız listelenir.

**U3. Rapor.** PR açıklamasına: kaç bulgu, kaçı kapandı, kalanların listesi; "tasarım yenilendi" **deme**, "N bulgu kapatıldı" de.

**Başla:** U1 (tam denetim, tek commit) → U2 (her düzeltme ayrı commit) → U3.
